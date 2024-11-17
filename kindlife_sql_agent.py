import json
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
import os
from dotenv import load_dotenv
from server_connection import hit_query

load_dotenv()

class NLToSQLConverter:
    def __init__(self, schema_path, GROQ_API):
        """Initialize the converter with schema path"""
        self.schema_path = schema_path
        self.llm = ChatGroq(
            api_key=GROQ_API,
            model_name="mixtral-8x7b-32768",  
            temperature=0,
            max_tokens = 4096
        )
        
        # self.response = 
        self.schema = self._load_schema()
        self.prompt = self._create_prompt_template()
        self.schema_context = self._format_schema_for_prompt()
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)

    def _load_schema(self):
        """Load and parse the schema file"""
        try:
            with open(self.schema_path, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            raise Exception(f"Schema file not found at {self.schema_path}")
        except json.JSONDecodeError:
            raise Exception("Invalid JSON in schema file")

    def _create_prompt_template(self):
        """Create the prompt template for SQL generation"""
        
        
        template = """You are an expert SQL query generator with deep understanding of both natural language and database schemas.
                Your goal is to accurately convert natural language questions into SQL queries based on the provided schema, ensuring precision 
                and efficiency and you can understand the natural query emotions, which is given in question analyze the question for the better 
                understanding to converting the natural language query into the SQL query.

        Database Schema:
        {schema} 
        
        Convert this natural language question into a SQL query:
        Question: {question}
        
        Requirements:
        1. Ensure the SQL query is **complete**, **correct**, and optimized for performance, addressing the business context.
        2. Use the provided schema as the foundation for the query.
        3. Fully understand the provided schema and **avoid using any irrelevant or unnecessary columns and table names**. Only use the columns that are relevant for answering the given question and providing in the schema.
        4. Focus on **clarity** and **efficiency** in your SQL. You should not create queries that are overly complex or inefficient.
        5. Always make use of **appropriate joins** based on the foreign key relationships in the schema to ensure data consistency.
        6. The SQL query should **only** include **required columns** from the tables, based on the question asked. Avoid selecting unnecessary columns which are not even present in the schema or additional data that is not directly related to the question.
        7. Always rembeber you are expert in MySQL, so queries should be accurate in MySQL format.
        8. Use MySQL-specific syntax and features
        9. Use proper table joins based on the foreign key relationships
        10. Return ONLY the SQL query without any explanations
        11. Consider performance by:
           - Using appropriate indexes for mysql
           - Using CTE (WITH clause) for complex queries and use only if required
           - Using EXPLAIN when needed for verification
        12. Use appropriate aggregation functions when needed
        13. Include proper WHERE clauses for filtering
        14. For time-based queries:
           
        SQL Query:"""
        
        return ChatPromptTemplate.from_template(template) 

    def _format_schema_for_prompt(self):
        """Format the schema in a readable way for the LLM"""
        formatted_schema = []
        for table in self.schema["Tables"]:
            table_desc = f"\nTable: {table['Name']}\n"
            table_desc += f"Description: {table['Instruction']}\n"
            table_desc += "Columns:\n"
            
            for prop in table["Properties"]:
                col_desc = f"- {prop['name']} ({prop['type']})"
                if prop.get("foreign_key_table_name"):
                    col_desc += f" -> References {prop['foreign_key_table_name']}"
                
                # Check if the 'instruction' key exists in the property dictionary
                instruction = prop.get('instruction', 'No description available')
                col_desc += f"\n  Description: {instruction}"
                
                table_desc += col_desc + "\n"
            
            formatted_schema.append(table_desc)
    
        return "\n".join(formatted_schema)

    def _clean_sql_query(self, sql_query):
        """Clean the SQL query by removing backslashes and forward slashes"""
        return sql_query.replace('\\', '')

    def generate_sql(self, question):
        """Generate SQL from natural language question"""
        try:
            response = self.chain.invoke({
                "schema": self._format_schema_for_prompt(),
                "question": question
            })
            sql_query = response["text"].strip()
            sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            # Clean the query before returning
            cleaned_query = self._clean_sql_query(sql_query)
            return cleaned_query
        except Exception as e:
            raise Exception(f"Error generating SQL: {str(e)}")

def main():
    GROQ_API = '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'
    
    schema_path = "schema.json"
    converter = NLToSQLConverter(schema_path, GROQ_API)
    
    # Example questions
    questions = [
        # "Show me top 5 of 'report_attendance_data_flat_table'."
        # "Show me the first 5 records from the report_attendance_data_flat_table table"
        # "List all locations with their shift timings"
        # "What is the average operator count for each company in February 2021?",
        # "Show me the name of column in the 'company_shifts' table?",
        # "Show me the average operator count for each company in January 2021"
        # "What is the total man power across all shifts for the PEE EMPRO company?"
        # "What is the total man power for the PEEEMPRO company?"
        # "Give me the attendance of the company DND"
        # "Show me top 5 records of Attendance Records"
        # "What is the best shift for the comapny DND?"
    ]
    
    print("Welcome to the NL to SQL converter!")
    print("Enter 'q' or 'exit' to quit the program.")
    print("-" * 80)
    
    while True:
        question = input("\nPlease provide your query here (or 'q'/'exit' to quit): ").strip()
        if question in ['q', 'exit']:
            print("\nThank you for using the NL to SQL converter. Goodbye!")
            break
            
        if not question:
            print("Please enter a valid query.")
            continue
        print(f"\nQuestion: {question}")
        print("Generated SQL:")
        try:
            sql = converter.generate_sql(question)
            print(sql)
            hit_query(sql)
        except Exception as e:
            print(f"Error: {str(e)}")
        print("-" * 80)

if __name__ == "__main__":
    main()