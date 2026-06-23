-- ReconHive schema (generated from SQLAlchemy metadata, PostgreSQL dialect)
-- Validates: every type, constraint, FK, and index compiles.

CREATE TYPE job_type AS ENUM ('discovery', 'port_scan', 'banner_grab', 'enrich');
CREATE TYPE job_status AS ENUM ('pending', 'authorizing', 'running', 'completed', 'failed', 'cancelled');
CREATE TYPE scope_kind AS ENUM ('allow', 'deny');
CREATE TYPE audit_action AS ENUM ('scope_decision', 'job_submitted', 'job_started', 'job_finished', 'scope_changed');
CREATE TYPE transport AS ENUM ('tcp', 'udp');

CREATE TABLE engagements (
	id UUID NOT NULL, 
	client_name VARCHAR(255) NOT NULL, 
	authorization_ref VARCHAR(255) NOT NULL, 
	contact VARCHAR(255), 
	starts_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ends_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	notes TEXT, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_engagements PRIMARY KEY (id), 
	CONSTRAINT ck_engagements_ends_after_starts CHECK (ends_at > starts_at)
);
CREATE INDEX ix_engagements_active ON engagements (is_active);

CREATE TABLE hosts (
	id UUID NOT NULL, 
	engagement_id UUID NOT NULL, 
	ip INET NOT NULL, 
	hostname VARCHAR(255), 
	asn INTEGER, 
	as_org VARCHAR(255), 
	country VARCHAR(2), 
	city VARCHAR(128), 
	latitude FLOAT, 
	longitude FLOAT, 
	os_guess VARCHAR(128), 
	tags TEXT[] NOT NULL, 
	first_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	last_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_hosts PRIMARY KEY (id), 
	CONSTRAINT ip UNIQUE (engagement_id, ip), 
	CONSTRAINT fk_hosts_engagement_id_engagements FOREIGN KEY(engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
);
CREATE INDEX ix_hosts_asn ON hosts (asn);
CREATE INDEX ix_hosts_country ON hosts (country);
CREATE INDEX ix_hosts_ip_gist ON hosts USING gist (ip);

CREATE TABLE scan_jobs (
	id UUID NOT NULL, 
	engagement_id UUID NOT NULL, 
	job_type job_type NOT NULL, 
	status job_status NOT NULL, 
	requested_targets TEXT[] NOT NULL, 
	authorized_targets TEXT[] NOT NULL, 
	rejected_targets TEXT[] NOT NULL, 
	requested_by VARCHAR(255) NOT NULL, 
	params JSONB NOT NULL, 
	stats JSONB NOT NULL, 
	error TEXT, 
	started_at TIMESTAMP WITH TIME ZONE, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_scan_jobs PRIMARY KEY (id), 
	CONSTRAINT fk_scan_jobs_engagement_id_engagements FOREIGN KEY(engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
);
CREATE INDEX ix_scan_jobs_engagement ON scan_jobs (engagement_id);
CREATE INDEX ix_scan_jobs_status ON scan_jobs (status);

CREATE TABLE scope_entries (
	id UUID NOT NULL, 
	engagement_id UUID NOT NULL, 
	cidr CIDR NOT NULL, 
	kind scope_kind NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE, 
	note VARCHAR(500), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_scope_entries PRIMARY KEY (id), 
	CONSTRAINT cidr_kind UNIQUE (engagement_id, cidr, kind), 
	CONSTRAINT fk_scope_entries_engagement_id_engagements FOREIGN KEY(engagement_id) REFERENCES engagements (id) ON DELETE CASCADE
);
CREATE INDEX ix_scope_entries_cidr_gist ON scope_entries USING gist (cidr);
CREATE INDEX ix_scope_entries_engagement ON scope_entries (engagement_id);

CREATE TABLE audit_log (
	id BIGSERIAL NOT NULL, 
	ts TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	engagement_id UUID, 
	job_id UUID, 
	actor VARCHAR(255) NOT NULL, 
	action audit_action NOT NULL, 
	target VARCHAR(255), 
	verdict VARCHAR(32), 
	reason TEXT, 
	detail JSONB NOT NULL, 
	CONSTRAINT pk_audit_log PRIMARY KEY (id), 
	CONSTRAINT fk_audit_log_engagement_id_engagements FOREIGN KEY(engagement_id) REFERENCES engagements (id) ON DELETE SET NULL, 
	CONSTRAINT fk_audit_log_job_id_scan_jobs FOREIGN KEY(job_id) REFERENCES scan_jobs (id) ON DELETE SET NULL
);
CREATE INDEX ix_audit_log_ts ON audit_log (ts);
CREATE INDEX ix_audit_log_engagement ON audit_log (engagement_id);
CREATE INDEX ix_audit_log_action ON audit_log (action);

CREATE TABLE services (
	id UUID NOT NULL, 
	host_id UUID NOT NULL, 
	port INTEGER NOT NULL, 
	transport transport NOT NULL, 
	product VARCHAR(255), 
	version VARCHAR(128), 
	extra_info VARCHAR(255), 
	cpe TEXT[] NOT NULL, 
	banner TEXT, 
	tls JSONB, 
	data JSONB NOT NULL, 
	search_vector TSVECTOR, 
	first_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	last_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_services PRIMARY KEY (id), 
	CONSTRAINT host_port UNIQUE (host_id, port, transport), 
	CONSTRAINT ck_services_port_range CHECK (port >= 0 AND port <= 65535), 
	CONSTRAINT fk_services_host_id_hosts FOREIGN KEY(host_id) REFERENCES hosts (id) ON DELETE CASCADE
);
CREATE INDEX ix_services_port ON services (port);
CREATE INDEX ix_services_search_gin ON services USING gin (search_vector);
CREATE INDEX ix_services_product ON services (product);

-- ---------------------------------------------------------------------------
-- Full-text search: keep services.search_vector current on any write.
-- The app also sets it on upsert; this trigger guarantees consistency for
-- direct SQL writes / backfills.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION services_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.product, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.version, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.banner,  '')), 'C');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_services_search_vector
    BEFORE INSERT OR UPDATE OF product, version, banner
    ON services
    FOR EACH ROW EXECUTE FUNCTION services_search_vector_update();
