-- Intention-to-treat denominator: all randomized eligible customers, including non-converters.
SELECT phase, corridor, price_multiplier, COUNT(*) AS eligible_customers,
       SUM(converted) AS converted_customers, AVG(converted * 1.0) AS conversion_rate,
       AVG(price_usd) AS assigned_price_usd,
       AVG(revenue_usd) AS revenue_per_eligible_customer,
       AVG(contribution_usd) AS contribution_per_eligible_customer
FROM experiments
GROUP BY phase, corridor, price_multiplier
ORDER BY phase, corridor, price_multiplier;
