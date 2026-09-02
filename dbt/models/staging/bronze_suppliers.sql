-- GENERATED from the china_ecommerce manifest by scripts/dbt_codegen.py. Do not edit by hand.
select * from read_csv_auto('domains/china_ecommerce/seed/structured/suppliers.csv', header=true, all_varchar=true)
