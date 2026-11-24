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
-- Student workload by due day (combine personal tasks and enrolled course work).
WITH items AS (
  SELECT user_id, due_at::date AS work_day, title, 'personal' AS source
  FROM personal_tasks WHERE NOT is_complete AND NOT is_archived
  UNION ALL
  SELECT e.user_id, d.due_at::date, d.title, 'course'
  FROM enrollments e JOIN deadlines d USING(course_id)
  LEFT JOIN submissions s ON s.deadline_id=d.deadline_id AND s.user_id=e.user_id
  WHERE e.status='active' AND d.is_active AND s.submission_id IS NULL
)
SELECT work_day, count(*) AS open_items, array_agg(title ORDER BY title) AS item_titles
FROM items WHERE user_id=:student_id GROUP BY work_day ORDER BY work_day;

-- Task completion history powers a private consistency streak, not a public ranking.
SELECT completed_at::date AS activity_day, count(*) AS tasks_completed
FROM task_completions WHERE user_id=:student_id
GROUP BY completed_at::date ORDER BY activity_day DESC;

-- Project workspace files are metadata only; binaries remain outside the relational DB.
SELECT p.name, t.title AS task_title, d.title AS course_deadline, f.file_name, f.uploaded_at
FROM projects p
LEFT JOIN personal_tasks t ON t.project_id=p.project_id AND t.user_id=p.user_id
LEFT JOIN project_deadlines pd ON pd.project_id=p.project_id AND pd.user_id=p.user_id
LEFT JOIN deadlines d ON d.deadline_id=pd.deadline_id
LEFT JOIN project_files f ON f.project_id=p.project_id
WHERE p.user_id=:student_id AND p.project_id=:project_id;
