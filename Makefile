db-up:
	docker-compose up mysql -d

db-down:
	docker-compose down

db-logs:
	docker logs platform-mysql-1

db-reset:
	docker-compose down -v
	docker-compose up mysql -d