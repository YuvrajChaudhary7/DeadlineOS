-- Course roster with JOIN
SELECT c.course_code,c.course_name,u.email,u.first_name,u.last_name FROM courses c JOIN enrollments e USING(course_id) JOIN users u USING(user_id) WHERE c.course_code=:course_code AND e.status='active' ORDER BY u.last_name;
-- Student dashboard through a view
SELECT * FROM upcoming_deadlines WHERE user_id=:student_id ORDER BY due_at;
-- Aggregated analytics
SELECT course_code,title,enrolled_count,submission_count,late_count,submission_pct FROM submission_stats ORDER BY course_code,title;
-- Grade plus audit row should be committed together
BEGIN;
UPDATE submissions SET marks_obtained=:marks,feedback=:feedback,status='graded',graded_by=:staff_id WHERE submission_id=:submission_id;
INSERT INTO activity_logs(user_id,action,entity_type,entity_id) VALUES(:staff_id,'grade','submission',:submission_id);
COMMIT;
