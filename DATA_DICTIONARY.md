# Synthetic customer experiment data

One row per randomized eligible customer. All values are independently invented.

| Field | Definition |
|---|---|
| customer_id | Unique synthetic randomized customer; IDs are disjoint across phases. |
| corridor | Fictional group A/B/C; no real commercial corridor mapping. |
| phase | screening or independent confirmation. |
| price_multiplier | Assigned price / control price; screening uses 0.8, 0.9, 1, 1.1, 1.2. |
| price_usd | All-in USD-equivalent charge; not separate fee and spread. |
| send_amount_usd | Fixed $300 principal in this isolated experiment. |
| converted | 0/1 observed conversion after price assignment. |
| variable_cost_usd | Processing cost per completed transaction; 30% of corridor control price, fixed across arms. |
| revenue_usd | converted × assigned price; zero for non-converters. |
| contribution_usd | converted × (assigned price − fixed variable cost). |
