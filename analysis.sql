SELECT d.name AS document_type, COUNT(*) AS requests
FROM requests r JOIN document_types d USING (type_id)
GROUP BY d.name
ORDER BY requests DESC;

SELECT d.name AS document_type,
       ROUND((AVG(EXTRACT(EPOCH FROM (h.ready_at - r.created_at))) / 3600)::numeric, 1) AS avg_hours,
       COUNT(*) AS ready_requests
FROM requests r
JOIN document_types d USING (type_id)
JOIN (SELECT request_id, MIN(changed_at) AS ready_at
      FROM status_history WHERE new_status = 'Ready' GROUP BY request_id) h USING (request_id)
GROUP BY d.name
ORDER BY avg_hours DESC;

SELECT date_trunc('week', created_at)::date AS week_start, COUNT(*) AS requests
FROM requests
GROUP BY week_start
ORDER BY week_start;
