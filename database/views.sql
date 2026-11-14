CREATE VIEW upcoming_deadlines AS
SELECT e.user_id, c.course_code, d.deadline_id, d.title, d.due_at, s.submission_id, s.status AS submission_status
FROM enrollments e JOIN courses c USING(course_id) JOIN deadlines d USING(course_id)
LEFT JOIN submissions s ON s.deadline_id=d.deadline_id AND s.user_id=e.user_id
WHERE e.status='active' AND d.is_active;

CREATE VIEW submission_stats AS
SELECT c.course_id,c.course_code,d.deadline_id,d.title,count(DISTINCT e.user_id) AS enrolled_count,
       count(s.submission_id) AS submission_count,count(*) FILTER (WHERE s.status='late') AS late_count,
       round(100.0*count(s.submission_id)/NULLIF(count(DISTINCT e.user_id),0),1) AS submission_pct
FROM courses c JOIN deadlines d USING(course_id)
LEFT JOIN enrollments e ON e.course_id=c.course_id AND e.status='active'
LEFT JOIN submissions s ON s.deadline_id=d.deadline_id AND s.user_id=e.user_id
GROUP BY c.course_id,c.course_code,d.deadline_id,d.title;

CREATE VIEW overdue_deadlines AS
SELECT d.deadline_id,d.course_id,d.title,d.due_at,e.user_id AS student_id,s.submission_id,s.submitted_at,s.status
FROM deadlines d JOIN enrollments e ON e.course_id=d.course_id AND e.status='active'
LEFT JOIN submissions s ON s.deadline_id=d.deadline_id AND s.user_id=e.user_id
WHERE d.is_active AND d.due_at<now() AND (s.submission_id IS NULL OR s.status='late');
