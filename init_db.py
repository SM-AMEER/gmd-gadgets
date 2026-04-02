import sqlite3
conn=sqlite3.connect("database.db")
c=conn.cursor()
c.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price INTEGER, image TEXT)")
c.execute("INSERT INTO products (name,price,image) VALUES ('Headphones',2000,'https://via.placeholder.com/200')")
conn.commit()
conn.close()
