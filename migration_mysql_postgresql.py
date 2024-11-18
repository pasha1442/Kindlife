import mysql.connector
import psycopg2
from psycopg2.extras import execute_values
import logging
from datetime import datetime
import sys

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def connect_mysql(host, user, password, database):
    """Connect to MySQL database"""
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            consume_results=True
        )
        logging.info("Successfully connected to MySQL database")
        return connection
    except mysql.connector.Error as e:
        logging.error(f"Error connecting to MySQL database: {e}")
        raise

def connect_postgresql(host, user, port, password, dbname):
    """Connect to PostgreSQL database"""
    try:
        connection = psycopg2.connect(
            host=host,
            user=user,
            port = port,
            password=password,
            database=dbname
        )
        logging.info("Successfully connected to PostgreSQL database")
        return connection
    except psycopg2.Error as e:
        logging.error(f"Error connecting to PostgreSQL database: {e}")
        raise

def get_mysql_tables(mysql_conn):
    """Get list of tables from MySQL database"""
    cursor = mysql_conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    # print(tables)
    cursor.close()
    return tables

def get_table_schema(mysql_conn, table):
    """Get column information for a table"""
    cursor = mysql_conn.cursor()
    cursor.execute(f"DESCRIBE {table}")
    columns = cursor.fetchall()
    # print(columns)
    cursor.close()
    return columns

def mysql_to_postgresql_type(mysql_type):
    """Convert MySQL data types to PostgreSQL data types"""
    type_mapping = {
        'tinyint': 'smallint',
        'smallint': 'smallint',
        'mediumint': 'integer',
        'int': 'bigint',  # Changed from integer to bigint
        'bigint': 'bigint',
        'decimal': 'numeric',
        'float': 'double precision',
        'double': 'double precision',
        'real': 'double precision',
        'varchar': 'varchar',
        'char': 'char',
        'text': 'text',
        'mediumtext': 'text',
        'longtext': 'text',
        'json': 'jsonb',
        'datetime': 'timestamp',
        'timestamp': 'timestamp',
        'date': 'date',
        'time': 'time',
        'boolean': 'boolean',
        'tinytext': 'text',
        'enum': 'varchar(255)',
        'set': 'varchar(255)',
        'binary': 'bytea',
        'varbinary': 'bytea',
        'blob': 'bytea',
        'mediumblob': 'bytea',
        'longblob': 'bytea'
    }
    
    # Extract base type (remove length specification)
    base_type = mysql_type.split('(')[0].lower()
    
    # Check if it's an unsigned int type
    if 'unsigned' in mysql_type.lower():
        if base_type == 'tinyint':
            return 'smallint'
        elif base_type == 'smallint':
            return 'integer'
        elif base_type in ('mediumint', 'int'):
            return 'bigint'
        elif base_type == 'bigint':
            return 'numeric(20)'  # For unsigned bigint that might exceed bigint range
    
    # Handle decimal/numeric with precision
    if base_type == 'decimal' and '(' in mysql_type:
        return mysql_type.replace('decimal', 'numeric')
    
    return type_mapping.get(base_type, 'text')

def create_postgresql_table(pg_conn, table_name, columns):
    """Create table in PostgreSQL with proper handling of primary keys"""
    cursor = pg_conn.cursor()
    
    # Separate primary key columns
    primary_key_columns = []
    column_defs = []
    
    for column in columns:
        name = column[0]
        mysql_type = column[1]
        is_nullable = "NULL" if column[2] == "YES" else "NOT NULL"
        is_primary = column[3] == "PRI"
        
        if is_primary:
            primary_key_columns.append(name)
        
        pg_type = mysql_to_postgresql_type(mysql_type)
        # Don't include PRIMARY KEY in individual column definitions
        column_def = f"{name} {pg_type} {is_nullable}".strip()
        column_defs.append(column_def)
    
    # Add primary key constraint at the table level if there are primary keys
    if primary_key_columns:
        pk_constraint = f", CONSTRAINT {table_name}_pkey PRIMARY KEY ({', '.join(primary_key_columns)})"
    else:
        pk_constraint = ""
    
    # Create table
    create_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        {', '.join(column_defs)}
        {pk_constraint}
    )
    """
    
    try:
        cursor.execute(create_query)
        pg_conn.commit()
        logging.info(f"Created table {table_name} in PostgreSQL")
    except psycopg2.Error as e:
        logging.error(f"Error creating table {table_name}: {e}")
        raise
    finally:
        cursor.close()

def migrate_data(mysql_conn, pg_conn, table_name, batch_size=1000):
    """Migrate data from MySQL to PostgreSQL"""
    mysql_cursor = mysql_conn.cursor(buffered=True)
    pg_cursor = pg_conn.cursor()
    
    try:
        # Get column names
        x = mysql_cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
        # print(table_name)
        columns = [desc[0] for desc in mysql_cursor.description]
        # print(columns)
        mysql_cursor.fetchall()
        
        # Get total count
        mysql_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_rows = mysql_cursor.fetchone()[0]
        
        # Fetch and insert data in batches
        mysql_cursor.execute(f"SELECT * FROM {table_name}")
        processed_rows = 0
        
        while True:
            rows = mysql_cursor.fetchmany(batch_size)
            if not rows:
                break
                
            # Insert batch into PostgreSQL
            insert_query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES %s
            """
            execute_values(pg_cursor, insert_query, rows)
            pg_conn.commit()
            
            processed_rows += len(rows)
            logging.info(f"Migrated {processed_rows}/{total_rows} rows from {table_name}")
            
    except (mysql.connector.Error, psycopg2.Error) as e:
        logging.error(f"Error migrating data for table {table_name}: {e}")
        raise
    finally:
        mysql_cursor.close()
        pg_cursor.close()

def main():
    # Setup logging
    logger = setup_logging()
    
    # Database configurations
    # MySQL connection settings
    mysql_config = {
        'host': '127.0.0.1',
        'user': 'akash',
        'password': 'Akash123!',
        'database': 'Kindlife'
    }

    # PostgreSQL connection settings
    pg_config = {
            'host': '127.0.0.1',
            'port': 5433,
            'user': 'akash',
            'password': 'auriga',
            'dbname': 'Kindlife'
    }
    
    try:
        # Connect to databases
        mysql_conn = connect_mysql(**mysql_config)
        pg_conn = connect_postgresql(**pg_config)
        
        # Get list of tables
        tables = get_mysql_tables(mysql_conn)
        
        # Migrate each table
        for table in tables:
            logging.info(f"Starting migration for table: {table}")
            
            # Get table schema
            columns = get_table_schema(mysql_conn, table)
            
            # Create table in PostgreSQL
            create_postgresql_table(pg_conn, table, columns)
            
            # Migrate data
            migrate_data(mysql_conn, pg_conn, table)
            
            logging.info(f"Completed migration for table: {table}")
            
    except Exception as e:
        logging.error(f"Migration failed: {e}")
        raise
    finally:
        # Close connections
        if 'mysql_conn' in locals():
            mysql_conn.close()
        if 'pg_conn' in locals():
            pg_conn.close()

if __name__ == "__main__":
    main()