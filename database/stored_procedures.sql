-- PostgreSQL examples; API performs the equivalent workflow in ORM transactions.
CREATE OR REPLACE FUNCTION submit_assignment(p_deadline BIGINT,p_student BIGINT,p_object_key TEXT)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE v_due TIMESTAMPTZ; v_id BIGINT;
BEGIN
  SELECT due_at INTO STRICT v_due FROM deadlines WHERE deadline_id=p_deadline AND is_active;
  IF NOT EXISTS(SELECT 1 FROM deadlines d JOIN enrollments e USING(course_id) WHERE d.deadline_id=p_deadline AND e.user_id=p_student AND e.status='active') THEN RAISE EXCEPTION 'active enrollment required'; END IF;
  INSERT INTO submissions(deadline_id,user_id,object_key,status) VALUES(p_deadline,p_student,p_object_key,CASE WHEN now()>v_due THEN 'late' ELSE 'submitted' END) RETURNING submission_id INTO v_id;
  RETURN v_id;
END $$;
CREATE OR REPLACE FUNCTION grade_submission(p_submission BIGINT,p_staff BIGINT,p_marks INTEGER,p_feedback TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE v_max INTEGER;
BEGIN
  SELECT d.max_marks INTO STRICT v_max FROM submissions s JOIN deadlines d USING(deadline_id) JOIN courses c USING(course_id) WHERE s.submission_id=p_submission AND c.staff_id=p_staff FOR UPDATE;
  IF p_marks<0 OR p_marks>v_max THEN RAISE EXCEPTION 'marks out of range'; END IF;
  UPDATE submissions SET marks_obtained=p_marks,feedback=p_feedback,graded_by=p_staff,status='graded' WHERE submission_id=p_submission;
END $$;
