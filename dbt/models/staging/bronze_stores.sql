-- GENERATED from the china_ecommerce manifest by scripts/dbt_codegen.py. Do not edit by hand.
select * from read_csv_auto('/Users/berlinwei/Desktop/面试项目/shopping_agent-main/domains/china_ecommerce/seed/structured/stores.csv', header=true, all_varchar=true)
