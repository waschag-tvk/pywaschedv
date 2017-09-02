# Specifications

* existing data has to be imported
* framework will be Django (Python)
* interface for managing users (LDAP?)
  * additionally manage confirmed status (user instructed about washing equipment usage)
* connection to Netz-AG (vereinskasse)

## Wasch-AG web

* machine booking info
  * dates, user etc.
  * history
* login/out → LDAP
* confirmation of new users
  * all login info with Netz-AG
* hardware interface
* price per wasch slot
  * other parameters (free wash count, late timeout etc.)
* tidy up homescreen (those repetitive user messages)

## Appointment

* time, user, machine, used
* pricing → functions instead of table (more flexible)
* refunding → check used

## Waschente

* use python too?

## Money

* credit to Netz-AG account
* money between Netz-AG ↔ Wasch-AG?
