-- =============================================================
-- Healthcare Claims – Showcase SQL Queries
-- Demonstrates: CTEs, window functions, aggregation, subqueries
-- =============================================================

-- 1. Total claims, patients, and spend
SELECT
    COUNT(*)                              AS total_claims,
    COUNT(DISTINCT bene_id)               AS unique_patients,
    SUM(inscclaimamtreimbursed)           AS total_reimbursed,
    ROUND(AVG(inscclaimamtreimbursed), 2) AS avg_reimbursed
FROM healthcare_claims;


-- 2. Top 10 providers by reimbursement using RANK()
SELECT provider, total_reimbursed, claim_rank
FROM (
    SELECT
        provider,
        SUM(inscclaimamtreimbursed)                         AS total_reimbursed,
        RANK() OVER (ORDER BY SUM(inscclaimamtreimbursed) DESC) AS claim_rank
    FROM healthcare_claims
    WHERE provider IS NOT NULL
    GROUP BY provider
)
WHERE claim_rank <= 10
ORDER BY claim_rank;


-- 3. Patient risk stratification using CASE + GROUP BY
SELECT
    CASE
        WHEN chroniccond_diabetes = 1 AND chroniccond_heartfailure = 1 THEN 'High'
        WHEN chroniccond_diabetes = 1 OR  chroniccond_heartfailure = 1 THEN 'Medium'
        ELSE 'Low'
    END                              AS risk_level,
    COUNT(DISTINCT bene_id)          AS patient_count,
    SUM(inscclaimamtreimbursed)      AS total_reimbursed
FROM healthcare_claims
GROUP BY
    CASE
        WHEN chroniccond_diabetes = 1 AND chroniccond_heartfailure = 1 THEN 'High'
        WHEN chroniccond_diabetes = 1 OR  chroniccond_heartfailure = 1 THEN 'Medium'
        ELSE 'Low'
    END
ORDER BY total_reimbursed DESC;


-- 4. Average length of stay by gender (DATE arithmetic)
SELECT
    CASE gender WHEN 1 THEN 'Male' WHEN 2 THEN 'Female' ELSE 'Unknown' END AS gender_label,
    COUNT(*)                                          AS total_claims,
    ROUND(AVG(dischargedt - admissiondt), 1)          AS avg_los_days,
    ROUND(AVG(inscclaimamtreimbursed), 2)             AS avg_reimbursed
FROM healthcare_claims
WHERE admissiondt IS NOT NULL AND dischargedt IS NOT NULL
GROUP BY gender
ORDER BY avg_los_days DESC;


-- 5. Month-over-month claim growth using LAG()
WITH monthly AS (
    SELECT
        TO_CHAR(claimstartdt, 'YYYY-MM')     AS month_label,
        COUNT(*)                             AS total_claims
    FROM healthcare_claims
    WHERE claimstartdt IS NOT NULL
    GROUP BY TO_CHAR(claimstartdt, 'YYYY-MM')
)
SELECT
    month_label,
    total_claims,
    LAG(total_claims) OVER (ORDER BY month_label) AS prev_month,
    total_claims - LAG(total_claims) OVER (ORDER BY month_label) AS delta,
    ROUND(
        (total_claims - LAG(total_claims) OVER (ORDER BY month_label))
        / NULLIF(LAG(total_claims) OVER (ORDER BY month_label), 0) * 100,
    1) AS pct_change
FROM monthly
ORDER BY month_label;


-- 6. Patients whose lifetime spend exceeds the overall average (subquery)
SELECT bene_id, lifetime_reimbursed
FROM (
    SELECT bene_id, SUM(inscclaimamtreimbursed) AS lifetime_reimbursed
    FROM healthcare_claims
    GROUP BY bene_id
)
WHERE lifetime_reimbursed > (
    SELECT AVG(total_spend)
    FROM (
        SELECT SUM(inscclaimamtreimbursed) AS total_spend
        FROM healthcare_claims
        GROUP BY bene_id
    )
)
ORDER BY lifetime_reimbursed DESC;


-- 7. Running total of reimbursement by claim date (window function)
SELECT
    claim_id,
    bene_id,
    claimstartdt,
    inscclaimamtreimbursed,
    SUM(inscclaimamtreimbursed)
        OVER (ORDER BY claimstartdt ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        AS running_total
FROM healthcare_claims
WHERE claimstartdt IS NOT NULL
ORDER BY claimstartdt
FETCH FIRST 50 ROWS ONLY;


-- 8. Claims where both chronic conditions present and LOS > 3 days
SELECT
    claim_id, bene_id, provider,
    admissiondt, dischargedt,
    (dischargedt - admissiondt)  AS los_days,
    inscclaimamtreimbursed
FROM healthcare_claims
WHERE chroniccond_diabetes    = 1
  AND chroniccond_heartfailure = 1
  AND (dischargedt - admissiondt) > 3
ORDER BY inscclaimamtreimbursed DESC;
