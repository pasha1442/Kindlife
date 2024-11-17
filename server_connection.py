import mysql.connector
from tabulate import tabulate

# Connect to the database
def hit_query(sql_query):
    try:
        conn = mysql.connector.connect(
            database="Kindlife",
            user="akash",
            password="Akash123!",
            host="127.0.0.1",
            port="3306"
        )
        
        # Create a cursor
        cur = conn.cursor()
        
        # Execute the SQL query
        cur.execute(sql_query)
        
        # Get the column names
        columns = [desc[0] for desc in cur.description]
        
        # Fetch results
        rows = cur.fetchall()
        for row in rows:
            print(row)
            
        # Print the results in a table format
        print(tabulate(rows, headers=columns, tablefmt="pretty"))

    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Close cursor and connection
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()