import psycopg2
import json
import time
import ollama

class Text2SqlSampleGenerator:
    def __init__(self, db_params, ollama_model='llama3'):
        # Set up database connection
        self.conn = psycopg2.connect(**db_params)
        self.cursor = self.conn.cursor()
        
        # Set Ollama model
        self.ollama_model = ollama_model

    def get_database_schema(self):
        """
        Dynamically generate a human-readable database schema description
        """
        # Fetch table information
        tables = [
            "Majors", "CourseDefinitions", "CourseOfferings", 
            "MajorsCourses", "MajorElectives", 
            "MajorElectivesRules", "Prerequisites"
        ]
        
        schema_description = "Database Schema:\n"
        
        for table in tables:
            # Fetch column information for each table
            self.cursor.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = LOWER('{table}')
            """)
            columns = self.cursor.fetchall()
            
            schema_description += f"\n{table} Table:\n"
            for column in columns:
                schema_description += f"- {column[0]} ({column[1]})\n"
        
        return schema_description

    def generate_with_ollama(self, messages):
        """
        Generate response using Ollama
        
        Args:
        messages (list): List of message dictionaries
        
        Returns:
        str: Generated response
        """
        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=messages,
                options={
                    'temperature': 0.3,
                    'num_predict': 300
                }
            )
            return response['message']['content'].strip()
        except Exception as e:
            print(f"Error generating response: {e}")
            return None

    def generate_sql_with_llm(self, nl_query, schema):
        """
        Generate SQL query using Ollama
        """
        messages = [
            {
                "role": "system", 
                "content": f"""You are an expert SQL query generator for a university course database. 
                Generate a precise SQL query that answers the given natural language question.

                {schema}

                Guidelines:
                - Use appropriate JOINs between tables
                - Be precise in filtering conditions
                - Ensure the query matches the exact intent of the natural language query
                - Only return the SQL query, without any additional explanation
                """
            },
            {
                "role": "user", 
                "content": f"Natural Language Query: {nl_query}"
            }
        ]
        return self.generate_with_ollama(messages)

    def fetch_random_context(self):
        """
        Fetch a random context from the database
        
        Returns:
        dict: Context containing major, course, year, semester details
        """
        # Fetch a random major
        self.cursor.execute("SELECT Major_Name FROM Majors ORDER BY RANDOM() LIMIT 1")
        major = self.cursor.fetchone()[0]
        
        # Fetch a random course for this major
        self.cursor.execute("""
            SELECT cd.Course_Code, cd.Course_Name 
            FROM CourseDefinitions cd
            JOIN CourseOfferings co ON cd.Course_Definition_ID = co.Course_Definition_ID
            JOIN Majors m ON co.Major_ID = m.Major_ID
            WHERE m.Major_Name = %s
            ORDER BY RANDOM() LIMIT 1
        """, (major,))
        course = self.cursor.fetchone()
        
        # Fetch a random year and semester
        self.cursor.execute("""
            SELECT Year, Semester 
            FROM CourseOfferings 
            ORDER BY RANDOM() LIMIT 1
        """)
        year, semester = self.cursor.fetchone()
        
        return {
            'major': major,
            'course_code': course[0] if course else None,
            'course_name': course[1] if course else None,
            'year': year,
            'semester': semester
        }

    def generate_nlq_with_llm(self, context):
        """
        Generate Natural Language Query using Ollama
        """
        messages = [
            {
                "role": "system", 
                "content": """You are an expert at generating diverse, realistic natural language queries 
                for a university course database. Generate a unique, student-like query that could 
                be used to extract information from the database. Consider different ways a student 
                might ask about courses, majors, prerequisites, and course details."""
            },
            {
                "role": "user", 
                "content": f"""Generate a natural language query based on these context details:
                Major: {context.get('major', 'N/A')}
                Course Code: {context.get('course_code', 'N/A')}
                Course Name: {context.get('course_name', 'N/A')}
                Year: {context.get('year', 'N/A')}
                Semester: {context.get('semester', 'N/A')}
                Prerequisite courses: {context.get('prerequisite_courses', 'N/A')}
                Elective options: {context.get('elective_options', 'N/A')}
                Required Major Electives: {context.get('required_major_electives', 'N/A')}
                
                Provide a query that a typical student might ask about their courses or academic requirements.

                Guidelines:
                - The queries should be from a perspective of a typical student asking about their course ouline.
                - Only return the natural language questions, without any additional explanation"""
            }
        ]
        return self.generate_with_ollama(messages)

    def generate_samples(self, num_samples=5):
        # Get database schema
        schema = self.get_database_schema()
        
        samples = []
        
        for _ in range(num_samples):
            # Get random context
            context = self.fetch_random_context()
            
            # Generate Natural Language Query
            nlq = self.generate_nlq_with_llm(context)
            
            # Generate corresponding SQL query
            sql_query = self.generate_sql_with_llm(nlq, schema)
            
            if nlq and sql_query:
                sample = {
                    "instruction": f"You are a powerful text-to-SQL model. Your task is to generate SQL queries based on the following schema:\n\n{schema}",
                    "input": nlq,
                    "output": sql_query
                }
                samples.append(sample)
            
            # Prevent rate limiting
            time.sleep(0.5)
        
        return samples

    def save_samples(self, samples, filename='samples.json'):
        with open(filename, 'w') as f:
            json.dump(samples, f, indent=2)
    
    def __del__(self):
        # Close database connection
        if hasattr(self, 'cursor'):
            self.cursor.close()
        if hasattr(self, 'conn'):
            self.conn.close()

# Example usage
if __name__ == "__main__":
    # Replace with your actual PostgreSQL connection details
    db_params = {
        "dbname": "vme_chatbot",
        "user": "readonlyuser",
        "password": "your_password",
        "host": "localhost",
        "port": "5432"
    }

    # Generate and save samples
    generator = Text2SqlSampleGenerator(db_params, ollama_model='llama3')
    samples = generator.generate_samples(5)
    generator.save_samples(samples)

    print(f"Generated {len(samples)} text-to-SQL samples and saved to samples.json")
