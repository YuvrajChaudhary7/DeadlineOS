-- PostgreSQL audit trigger; the API also writes actor-aware audit rows.
CREATE OR REPLACE FUNCTION audit_submission_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO activity_logs(user_id,action,entity_type,entity_id)
  VALUES(COALESCE(NEW.user_id,OLD.user_id),TG_OP,'submission',COALESCE(NEW.submission_id,OLD.submission_id));
  RETURN COALESCE(NEW,OLD);
END $$;
CREATE TRIGGER trg_submission_audit AFTER INSERT OR UPDATE ON submissions
FOR EACH ROW EXECUTE FUNCTION audit_submission_change();
-- UNIQUE(deadline_id,user_id) is the concurrency-safe duplicate submission guard.
