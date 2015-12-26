#!/bin/bash -e
#
# Utility to auto-migrate with checkout. After checkout, all migrations that are not present in the
# new branch are unapplied and all migrations that were not present in the old branch are
# reapplied. So jumping between branches should keep the database structure compatible with code.
#
# WARNING: Unapplying migrations may delete data! The script is NOT to be used in production
# environment.
#
# Usage: ./checkout-and-migrate.sh <branch>
#

old_branch="$(git symbolic-ref --short HEAD)"
new_branch="$1"

# Inspect migrations in the old branch
declare -a old_migrations
app=""
while read line; do
  if [[ "$line" == "[X] "* ]]; then
    migration="${line#"[X] "}"
    old_migrations+=("$app:$migration")
  elif [[ "$line" == "[ ] "* ]]; then
    true # Skip unapplied migrations
  else
    app="$line"
  fi
done < <(env/bin/python manage.py migrate --list)

# Check out the new branch
git checkout "$new_branch"

# Inspect migrations in the new branch
declare -a new_migrations
app=""
while read line; do
  if [[ "$line" == "[X] "* ]]; then
    migration="${line#"[X] "}"
    new_migrations+=("$app:$migration")
  elif [[ "$line" == "[ ] "* ]]; then
    true # Skip unapplied migrations
  else
    app="$line"
  fi
done < <(env/bin/python manage.py migrate --list)

# Return back to the old branch
git checkout "$old_branch"

# Find last common migrations
declare -A common_migrations
declare -A last_migrations
for migration in "${old_migrations[@]}"; do
  app="${migration%:*}"
  name="${migration#*:}"
  common_migrations["$app"]="zero"
  last_migrations["$app"]="$name"
done
for migration in "${old_migrations[@]}"; do
  if [[ " ${new_migrations[*]} " == *" $migration "* ]]; then
    app="${migration%:*}"
    name="${migration#*:}"
    common_migrations["$app"]="$name"
  fi
done

# Revert to last common migrations (unless the last common migration is the very last migration).
for app in "${!common_migrations[@]}"; do
  name="${common_migrations[$app]}"
  last="${last_migrations[$app]}"
  if [[ "$name" != "$last" ]]; then
    env/bin/python manage.py migrate "$app" "$name"
  fi
done

# Finally, check out the new branch again and run migrations in the new branch.
git checkout "$new_branch"
env/bin/python manage.py migrate
