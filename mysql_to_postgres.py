import mysql.connector
import psycopg2
from psycopg2 import sql
from datetime import datetime, date
import logging
import sys


# MySQL connection settings
mysql_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'Auriga@123',
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

diff_tables = []


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

def transfer_data(mysql_table_name, pg_table_name):
    rows_processed = 0
    rows_failed = 0
    
    try:
        logging.info(f"Starting transfer for table: {mysql_table_name}")
        
        # Connect to MySQL
        mysql_conn = mysql.connector.connect(**mysql_config)
        mysql_cursor = mysql_conn.cursor(dictionary=True)

        # Connect to PostgreSQL
        pg_conn = psycopg2.connect(**pg_config)
        pg_cursor = pg_conn.cursor()
        
        # Disable triggers temporarily
        pg_cursor.execute(f"ALTER TABLE {pg_table_name} DISABLE TRIGGER ALL;")
        logging.info(f"Disabled triggers for table: {pg_table_name}")

        # Get total rows count
        mysql_cursor.execute(f"SELECT COUNT(*) as count FROM {mysql_table_name}")
        total_rows = mysql_cursor.fetchone()['count']
        logging.info(f"Total rows to process: {total_rows}")

        # Retrieve columns from MySQL table
        mysql_cursor.execute(f"DESCRIBE {mysql_table_name}")
        columns = mysql_cursor.fetchall()
        select_columns_dict = {}
        select_columns = []
        
        # Get PostgreSQL column types
        pg_cursor.execute(f"""
            SELECT column_name, data_type, character_maximum_length 
            FROM information_schema.columns 
            WHERE table_name = '{pg_table_name}'
        """)
        pg_column_types = dict((name, (type_, length)) for name, type_, length in pg_cursor.fetchall())

        for column in columns:
            col_type = column['Type']
            col_name = column['Field'].lower()
            # Convert bytes to string if necessary
            if isinstance(col_type, bytes):
                col_type = col_type.decode('utf-8')
            select_columns_dict[col_name] = col_type
            if col_type in ['point', 'polygon', 'linestring']:
                select_columns.append(f'ST_AsText({col_name}) AS {col_name}')
            else:
                select_columns.append(f'{mysql_table_name}.{col_name}')

        # Fetch data in batches
        batch_size = 1000
        mysql_cursor.execute(f"SELECT {', '.join(select_columns)} FROM {mysql_table_name}")
        
        while True:
            rows = mysql_cursor.fetchmany(batch_size)
            if not rows:
                break
                
            for row in rows:
                column_names = []
                values = []
                
                try:
                    for key, value in row.items():
                        key = key.lower()
                        pg_type = pg_column_types.get(key, ('unknown', None))[0].upper()

                        # Handle different data types
                        if value is None:
                            values.append(None)
                        elif isinstance(value, int):
                            # Handle integer types based on PostgreSQL column type
                            if pg_type == 'INTEGER':
                                if value > 2147483647:
                                    logging.warning(f"Integer overflow in column {key}: {value} -> 2147483647")
                                    value = 2147483647
                                elif value < -2147483648:
                                    logging.warning(f"Integer underflow in column {key}: {value} -> -2147483648")
                                    value = -2147483648
                            elif pg_type == 'BIGINT':
                                if value > 9223372036854775807:
                                    value = 9223372036854775807
                                elif value < -9223372036854775808:
                                    value = -9223372036854775808
                            
                            # Handle boolean conversion for tinyint(1)
                            col_type = select_columns_dict.get(key, '')
                            if isinstance(col_type, str) and col_type.startswith('tinyint(1)') and pg_type == 'BOOLEAN':
                                values.append(bool(value))
                            else:
                                values.append(value)

                        elif isinstance(value, (datetime, date)):
                            values.append(value.isoformat() if value else None)
                        elif isinstance(value, str):
                            # Handle string length limits
                            max_length = pg_column_types.get(key, (None, None))[1]
                            if max_length and len(value) > max_length:
                                logging.warning(f"Truncating string in column {key}: {len(value)} -> {max_length}")
                                value = value[:max_length]
                            values.append(value)
                        else:
                            values.append(value)
                            
                        column_names.append(f'"{key}"')

                    insert_query = f"""
                        INSERT INTO {pg_table_name} ({', '.join(column_names)}) 
                        VALUES ({', '.join(['%s'] * len(values))})
                    """
                    pg_cursor.execute(insert_query, values)
                    rows_processed += 1

                    # Commit every 1000 rows
                    if rows_processed % 1000 == 0:
                        pg_conn.commit()
                        logging.info(f"Processed {rows_processed}/{total_rows} rows")
                    
                except (psycopg2.IntegrityError, psycopg2.DataError) as e:
                    pg_conn.rollback()
                    rows_failed += 1
                    logging.error(f"Error in table {mysql_table_name}, row {rows_processed + rows_failed}: {str(e)}")
                    continue

            # Commit any remaining rows
            pg_conn.commit()

        # Final commit
        pg_conn.commit()
        logging.info(f"Table {mysql_table_name} completed. Processed: {rows_processed}, Failed: {rows_failed}")

    except Exception as e:
        logging.error(f"Major error in table {mysql_table_name}: {str(e)}", exc_info=True)
        raise

    finally:
        try:
            pg_cursor.execute(f"ALTER TABLE {pg_table_name} ENABLE TRIGGER ALL;")
            logging.info(f"Re-enabled triggers for table: {pg_table_name}")
        except Exception as e:
            logging.error(f"Error re-enabling triggers: {str(e)}")
            
        for cursor in [mysql_cursor, pg_cursor]:
            if cursor:
                cursor.close()
        for conn in [mysql_conn, pg_conn]:
            if conn:
                conn.close()
                
                
def transfer_all_tables():
    try:
        # Connect to MySQL
        mysql_conn = mysql.connector.connect(**mysql_config)
        mysql_cursor = mysql_conn.cursor(dictionary=True)

        pg_conn = psycopg2.connect(**pg_config)
        pg_cursor = pg_conn.cursor()

        logging.info("Starting full database transfer")

        mysql_cursor.execute("SHOW TABLES")
        tables = mysql_cursor.fetchall()
        total_tables = len(tables)
        processed_tables = 0

        for table in tables:
            db_name = mysql_config.get('database', 'digin_database')
            table_name = table.get(f'Tables_in_{db_name}', '')
            
            if table_name and table_name not in diff_tables:
                try:
                    logging.info(f"Processing table {processed_tables + 1}/{total_tables}: {table_name}")
                    transfer_data(table_name, table_name)
                    processed_tables += 1
                except Exception as e:
                    logging.error(f"Failed to transfer table {table_name}: {str(e)}")
                    continue

        # Update sequences
        logging.info("Updating sequences")
        pg_cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = pg_cursor.fetchall()
        for table in tables:
            table_name = table[0]
            try:
                pg_cursor.execute(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = '{table_name}' AND column_name = 'id';
                """)
                id_exists = pg_cursor.fetchone()
                if id_exists:
                    pg_cursor.execute(f"""
                        SELECT setval('{table_name}_id_seq', COALESCE((SELECT MAX(id) FROM {table_name}), 1));
                    """)
                    pg_conn.commit()
                    logging.info(f"Updated sequence for table: {table_name}")
            except Exception as e:
                logging.error(f"Error updating sequence for table {table_name}: {str(e)}")

        logging.info(f"Database transfer completed. Processed {processed_tables}/{total_tables} tables")

    except Exception as e:
        logging.error(f"Critical error during database transfer: {str(e)}", exc_info=True)

    finally:
        for cursor in [mysql_cursor, pg_cursor]:
            if cursor:
                cursor.close()
        for conn in [mysql_conn, pg_conn]:
            if conn:
                conn.close()

# Start the transfer process
if __name__ == "__main__":
    try:
        transfer_all_tables()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)