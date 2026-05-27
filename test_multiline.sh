val='{
  "type": "service_account"
}'
key="JSON"
# Using single quotes for docker compose
# We need to escape single quotes inside val if any
val_escaped=$(echo "$val" | sed "s/'/'\\\\''/g")
echo "$key='$val_escaped'" > test.env
cat test.env
