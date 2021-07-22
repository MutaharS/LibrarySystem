import psycopg2
from enum import Enum
import datetime
from getpass import getpass

# Format for DATE
FORMAT = "%m/%d/%Y" 

# UserType enumeration
class UserType(Enum):
    LIBRARIAN = 1
    PATRON = 2
    ANONYMOUS = 3

# Database class
class DataBase():
    # Get the librarian connection
    def get_librarian_connection(self):
        # If librarian, then connect like this
        connection = psycopg2.connect(
            host="localhost",
            port = 5432, 
            database="bookstore", 
            user="librarian", 
            password="password"
        )
        return connection

    # Get the Patron (Default) connection
    def get_patron_connection(self):
        # Connect Patron (default)
        connection = psycopg2.connect(
            host="localhost", 
            port = 5432, 
            database="bookstore", 
            user="patron", 
            password="password"
        )
        return connection
    
    # Clean input function (remove ' from input ) for SQL injection defense
    def get_clean_input(self, message):
        return input(message).replace('\'', '')

    def get_clean_password(self, message):
        return getpass(prompt='Password: ', stream=None).replace('\'', '')

    # Description: can return a query result (one query as a dictionary)
    # This is useful for returning the user information 
    # as a mapping of attribute to value
    # rather than indexing through it like an array
    # Function: Take database cursor and return fetchone() as a dict(attribute,value)
    def result_to_dict(self, cursor, result):
        keys   = cursor.description
        keys   = [col[0] for col in keys] # description returns Column('attributename','typecode')
        values = result
        data   = dict(zip(keys,values))
        return data

# Form validation 
def validate_form(formdata, cursor):
    firstname = formdata['firstname']
    lastname  = formdata['lastname']
    email     = formdata['email']
    dob       = formdata['dob']
    password  = formdata['password']
    # If anything is empty
    if len(firstname) == 0 or len(lastname) == 0 or len(dob) == 0 or len(password) == 0:
        print('Sorry, all fields are required')
        return False
    
    # If the email already exists
    cursor.execute("SELECT * FROM LibraryUsers WHERE email = %s", [email])
    if cursor.fetchone() != None:
        print('Sorry, that email has already been used')
        return False

    # If email does not have @ or ends in com,org,edu
    if not email.endswith('com') and not email.endswith('org') and not email.endswith('edu'):
        print("Invalid email entered")
        return False
    if not '@' in email:
        print("Invalid email entered")
        return False

    # DOB format should be "MM/DD/YYYY"
    try:
        datetime.datetime.strptime(dob, FORMAT)
    except ValueError:
        print("This is the incorrect date format. It should be DD/MM/YYYY")
        return False
    return True

class Views():
    def sign_up_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_patron_connection()
        cursor = connection.cursor()

        # Replace ' to prevent SQL injection
        firstname = db.get_clean_input('Enter first name: ')
        lastname  = db.get_clean_input('Enter last name: ')
        dob       = db.get_clean_input('Enter date of birth: ')
        email     = db.get_clean_input('Enter email: ')
        password  = db.get_clean_password('Enter password: ')

        # Check if the form is valid
        valid = validate_form(
            {
                'firstname' : firstname,
                'lastname'  : lastname,
                'dob'       : dob,
                'email'     : email,
                'password'  : password
            },
            cursor
        )

        if valid:
            cursor.execute(
                """INSERT INTO LibraryUsers(email,firstname,lastname,dob,isadmin,password) 
                VALUES (%s, %s, %s, %s, %s, %s)""", 
                (email,firstname,lastname,dob,'N',password)
            )
            connection.commit()
            print('Patron signup successful\n')

        cursor.close()
        connection.close()

    def login_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_patron_connection()
        cursor = connection.cursor()

        # Ask user for email and password
        email    = db.get_clean_input('Email: ')
        password = db.get_clean_password('Password: ')

        # Get user with that email and password
        cursor.execute("""SELECT email,isadmin FROM LibraryUsers WHERE email = %s AND password = %s""",(email,password))
        result = cursor.fetchone() # [email,isadmin]

        # Return the result of the query which is either:
        #   None         (unsuccessful login)
        #   query result (if successful login)
        if result == None:
            print('Sorry, we could not authenticate your credentials.')
            print('Returning to the main menu.\n')
            return None
        print('Login successful.\n')
        return db.result_to_dict(cursor,result)

    def assign_book_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_librarian_connection()
        cursor = connection.cursor()

        # Ask user for email and isbn
        print('Assign book: [patron email][book isbn]')
        email    = db.get_clean_input('Patron email: ')
        isbn     = db.get_clean_input('ISBN: ')

        # Get book with that isbn
        #cursor.execute("""SELECT email,isadmin FROM LibraryUsers WHERE email = %s AND password = %s""",(email,password))
        cursor.execute("""SELECT * FROM Books WHERE isbn = %s""", (isbn,))
        book = cursor.fetchone() # result of query

        if book == None:
            print('Could not find the book.')
            return None
        book = db.result_to_dict(cursor,book)       # get attribute -> value

        # Make sure quantity > 0
        cursor.execute("SELECT * FROM Inventory WHERE isbn = %s", (book['isbn'],))
        inventory = cursor.fetchone()
        inventory = db.result_to_dict(cursor,inventory)
        
        # get the quantity and make sure the book is available
        quantity = int(inventory['quantity'])
        if quantity < 1:
            # Get the most recent due date for that book
            cursor.execute("SELECT duedate FROM Borrow WHERE isbn = %s ORDER BY duedate LIMIT 1", (book['isbn'],))
            query = cursor.fetchone() # not actually duedate it is array[duedate]
            next_available_date = datetime.datetime.strftime(query[0], FORMAT)
            print('Sorry, that book is out of stock. It will be available on ' + next_available_date)
            return None

        # Get user with that email
        cursor.execute("""SELECT * FROM LibraryUsers WHERE email = %s""", (email,))
        patron = cursor.fetchone() # result of query

        # Check if the patron was found
        if patron == None:
            print('Could not find the patron.')
            return None
        patron = db.result_to_dict(cursor,patron)   # get attribute -> value

        # Format for our dates
        today = datetime.datetime.today()                       # get today as datetime obj
        strToday = datetime.datetime.strftime(today, FORMAT)
        duedate = today + datetime.timedelta(days=14)
        strDuedate = datetime.datetime.strftime(duedate, FORMAT)

        cursor.execute(
                """INSERT INTO Borrow(isbn,email,borrowdate,duedate) 
                VALUES (%s, %s, %s, %s)""", 
                (book['isbn'],patron['email'],strToday,strDuedate)
        )

        print('Successfully checked book out to {}. \'{}\' is due on {}.'.format(
                patron['firstname'] + ' ' + patron['lastname'],book['title'], strDuedate
            )
        )

        # Update inventory, setting that book's quantity - 1
        cursor.execute("UPDATE Inventory SET quantity = quantity - 1 WHERE isbn = %s", (book['isbn'],))

        connection.commit()
        cursor.close()
        connection.close()
    
    def process_return_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_librarian_connection()
        cursor = connection.cursor()

        # Ask user for email and isbn
        print('Assign book: [patron email][book isbn]')
        email    = db.get_clean_input('Patron email: ')
        isbn     = db.get_clean_input('ISBN: ')

        # Get book with that isbn
        cursor.execute("""SELECT * FROM Books WHERE isbn = %s""", (isbn,))
        book = cursor.fetchone() # result of query

        if book == None:
            print('Could not find the book.')
            return None
        book = db.result_to_dict(cursor,book)       # get attribute -> value

        # Get user with that email
        cursor.execute("""SELECT * FROM LibraryUsers WHERE email = %s""", (email,))
        patron = cursor.fetchone() # result of query

        # Check if the patron was found
        if patron == None:
            print('Could not find the patron.')
            return None
        patron = db.result_to_dict(cursor,patron)   # get attribute -> value
        
        # Get the borrowdate and duedate from the borrow record
        cursor.execute("SELECT * FROM Borrow WHERE email = %s AND isbn = %s", (email,isbn))
        query = cursor.fetchone()

        # If query is None, then we couldn't find that patron with that book (email,isbn)
        if query == None:
            print('Not showing that you have borrowed this book.')
            print("Please check the email and ISBN again.")
            return None

        borrow_record = db.result_to_dict(cursor,query)

        today = datetime.date.today()      # date object
        duedate = borrow_record['duedate'] # date object
        days_overdue_obj = today - duedate
        days_overdue = days_overdue_obj.days
        # Charge them if the book is overdue
        if(days_overdue > 0):
            charge = days_overdue * 0.25
            print('Your book is overdue by {} many days. Charge incurred: ${}'.format(str(days_overdue),str(charge)))
        else:
            print('Thank you for returning your book on time. We appreciate it.')
        
        # Delete the borrow entry
        cursor.execute("DELETE FROM Borrow WHERE email = %s AND isbn = %s", (email,isbn))

        # Update the inventory
        cursor.execute("UPDATE Inventory SET quantity = quantity + 1 WHERE isbn = %s", (isbn,))

        connection.commit()
        cursor.close()
        connection.close()
    
    def overdue_books_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_librarian_connection()
        cursor = connection.cursor()

        # Get all the books from Borrow that are overdue
        cursor.execute("SELECT * FROM Borrow WHERE duedate < CURRENT_DATE")
        query = cursor.fetchall()
        overduebooks = [db.result_to_dict(cursor,item) for item in query]
        current_date = datetime.datetime.strftime(datetime.date.today(), FORMAT)
        print('------------------------------------------------')
        print('Overdue Books (Current Date: {}):'.format(current_date))
        print('------------------------------------------------')
        i = 0
        for book in overduebooks:
            print('ISBN: '          + book['isbn'])
            print('Patron Email: '  + book['email'])
            print('Borrow Date: '   + datetime.datetime.strftime(book['borrowdate'], FORMAT))
            print('Due Date: '      + datetime.datetime.strftime(book['duedate'], FORMAT))
            i = i + 1
            if i != len(query):
                print('------------------------------------------------')
        print('\n')

        cursor.close()
        connection.close()



    """  Patron Views  """
    
    def search_by_subject_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_patron_connection()
        cursor = connection.cursor()

        # Get the list of available subjects
        cursor.execute("SELECT DISTINCT subject FROM Books")
        query = cursor.fetchall()
        subjects = [item[0] for item in query]

        print('---------------- Search Menu ----------------')
        print('Select subject: ')
        for i in range(1,len(subjects)+1):
            print(str(i) + ': ' + subjects[i-1])
        cmd = input('Selection: ')

        try:
            cmd = int(cmd)
        except ValueError:
            print('Sorry, that was not a valid selection.')
            return None

        # Check that they did not select invalid integer
        if cmd > len(subjects):
            print('Sorry, that was not a valid selection.')
            return None

        # Get the subject
        subject = subjects[cmd-1]
        cursor.execute(  """SELECT title,isbn,
	                            STRING_AGG(
		                            firstname || ' ' || lastname, ', '
	                            ) AS Authors
                            FROM Books NATURAL JOIN WrittenBy NATURAL JOIN Authors 
                            WHERE subject = %s GROUP BY ISBN;""", (subject,))
        query = cursor.fetchall()
        query = [db.result_to_dict(cursor,item) for item in query]

        print('------------------------------------------------')
        print('Search Results: ')
        print('------------------------------------------------')
        i = 0
        for book in query:
            print('Title: '  + book['title'])
            print('Author(s): ' + book['authors'])
            print('ISBN: '   + book['isbn'])
            i = i + 1
            if i != len(query):
                print('------------------------------------------------')
        print('\n')

        cursor.close()
        connection.close()

    def search_by_author_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_patron_connection()
        cursor = connection.cursor()

        # Get author last name from user
        author_last_name = db.get_clean_input('Please enter the author\'s last name: ')

        # Get the books written by that author
        cursor.execute("""SELECT Title, FirstName, LastName, subject, datepublished, ISBN FROM Books 
                    NATURAL JOIN WrittenBy NATURAL JOIN Authors 
                    WHERE lastname = %s ORDER BY firstname,lastname""", (author_last_name,))
        
        query = cursor.fetchall()
        if len(query) == 0:
            print('Sorry, we do not carry books by that author.\n')
            return None

        query = [db.result_to_dict(cursor,item) for item in query]

        print('------------------------------------------------')
        print('Search Results: ')
        print('------------------------------------------------')
        i = 0
        for book in query:
            print('Title: '          + book['title'])
            print('Subject: '        + book['subject'])
            print('Date Published: ' + datetime.datetime.strftime(book['datepublished'], FORMAT))
            print('Author: '         + book['firstname'] + ' ' + book['lastname'])
            print('ISBN: '           + book['isbn'])
            i = i + 1
            if i != len(query):
                print('------------------------------------------------')
        print('\n')

        cursor.close()
        connection.close()

    def borrowed_books_view(self, email):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_patron_connection()
        cursor = connection.cursor()

        # Get all the books the user is borrowing
        cursor.execute("SELECT title,duedate FROM Borrow NATURAL JOIN Books WHERE email = %s", (email,))
        query = cursor.fetchall()

        # Convert list of tuples, to list of dictionaries
        query = [db.result_to_dict(cursor,item) for item in query]

        # Print out the results (print how many days till due, or if overdue)
        print('------------------------------------------------')
        print('My Borrowed Books: ')
        print('------------------------------------------------')
        i = 0
        for book in query:
            today = datetime.date.today()               # date object
            days_overdue_obj = today - book['duedate']  # date - date
            days_overdue = days_overdue_obj.days

            print('Title: '     + book['title'])
            # If the book is overdue
            if days_overdue > 0:
                charge = days_overdue * 0.25
                print('Your book is overdue. Please return as soon as possible.')
                print('Current overdue charge: {}'.format(charge))
            elif days_overdue == 0:
                print('Your book is due today. Please return')
                print('by 11:59 PM to avoid incurring an overdue charge.')
            else:
                print('This book is due in {} days.'.format( str(days_overdue*-1) ))
            i = i + 1
            if i != len(query):
                print('------------------------------------------------')
        print('\n')

        # Close the db connection
        cursor.close()
        connection.close()

    def book_recommendation_view(self):
        # Get DB connection class
        db = DataBase()

        # Get the DB cursor
        connection = db.get_patron_connection()
        cursor = connection.cursor()

        # Get the list of available subjects
        cursor.execute("SELECT DISTINCT subject FROM Books")
        query = cursor.fetchall()
        subjects = [item[0] for item in query]

        print('---------------- Book Recommendation ----------------')
        print('Select subject: ')
        for i in range(1,len(subjects)+1):
            print(str(i) + ': ' + subjects[i-1])
        cmd = input('Selection: ')

        try:
            cmd = int(cmd)
        except ValueError:
            print('Sorry, that was not a valid selection.')
            return None

        # Check that they did not select invalid integer
        if cmd > len(subjects):
            print('Sorry, that was not a valid selection.')
            return None
        
        # Get the subject
        subject = subjects[cmd-1]
        cursor.execute("""SELECT Title, FirstName, LastName, ISBN FROM Books 
                          NATURAL JOIN WrittenBy NATURAL JOIN Authors 
                          WHERE subject = %s ORDER BY RANDOM() LIMIT 1""", (subject,))

        query = cursor.fetchone()
        book = db.result_to_dict(cursor,query)

        # Print out the recommended book
        print('------------------------------------------------')
        print('Here is your recommendation: ')
        print('------------------------------------------------')
        print('Title: '  + book['title'])
        print('Author: ' + book['firstname'] + ' ' + book['lastname'])
        print('ISBN: '   + book['isbn'])
        print('\n')
        # Close the db connection
        cursor.close()
        connection.close()
        

def MainLoop():
    # Session to hold any session data for keeping track of system state
    session_data = {}
    session_data['user'] = UserType.ANONYMOUS

    # While user has not quit, run the main loop
    run_loop = True

    while run_loop:
        # Anonymous User menu
        if session_data['user'] == UserType.ANONYMOUS:
            print('---------------- Main Menu ----------------')
            print('Select Option: ')
            print('1: Sign up')
            print('2: Login')
            print('q: quit')
            cmd = input('Selection: ')
            
            if cmd == '1':
                print('Send to sign up view')
                view = Views()
                view.sign_up_view()
            if cmd == '2':
                print('Send to login view')
                view = Views()

                # Get result of logging in as a dictionary with email and isadmin
                result = view.login_view() # keys are 'email' and 'isadmin'
                if result == None:
                    # This means the user was not logged in successfully
                    continue

                # Set the session data for the logged in user
                # Save the appropriate user type in session_data
                if result['isadmin'] == 'Y':
                    # Set the user type to librarian
                    session_data['user']  = UserType.LIBRARIAN
                elif result['isadmin'] == 'N':
                    # Set the user type to patron
                    session_data['user'] = UserType.PATRON

                # Save the user email in session_data (email is pk in LibraryUsers table)
                session_data['email'] = result['email']
            elif cmd == 'q':
                run_loop = False
                print('Goodbye.')

        # Librarian User menu
        if session_data['user']== UserType.LIBRARIAN:
            print('---------------- Librarian Menu ({})----------------'.format(session_data['email']))
            print('Select Option: ')
            print('1: Assign book to patron')   # Main feature -DONE
            print('2: Process book return')     # Main feature -DONE
            print('3: View book catalog')       # Extra feature
            print('4: View registered patrons') # Extra feature
            print('5: View overdue books')      # Extra feature
            print('q: quit')
            cmd = input('Selection: ')

            if cmd   == '1':
                view = Views()
                view.assign_book_view()
            elif cmd == '2':
                view = Views()
                view.process_return_view()
            elif cmd == '3':
                print('View book catalog.')
            elif cmd == '4':
                print('View registered patrons')
            elif cmd == '5':
                view = Views()
                view.overdue_books_view()
            elif cmd == 'q':
                run_loop = False
                print('Goodbye.')
        
        # Patron User Menu
        if session_data['user'] == UserType.PATRON:
            print('---------------- Patron Menu ({}) ----------------'.format(session_data['email']))
            print('Select Option: ')
            print('1: Search by subject')           # Main feature  -DONE
            print('2: Search by author')            # Main feature  -DONE
            print('3: View my borrowed books')      # Extra feature -DONE
            print('4: Get a book recommendation')   # Extra feature -DONE
            print('q: quit')
            cmd = input('Selection: ')

            if cmd   == '1':
                view = Views()
                view.search_by_subject_view()
            elif cmd == '2':
                view = Views()
                view.search_by_author_view()
            elif cmd == '3':
                view = Views()
                view.borrowed_books_view(email=session_data['email'])
            elif cmd == '4':
                view = Views()
                view.book_recommendation_view()
            elif cmd == 'q':
                run_loop = False
                print('Goodbye.')

            
# Run the Main event loop
MainLoop()

# Project Overview

# Regular User FUNCTIONALITY
# signup view
# login view
# search view
    # Do you want to search by subject
        # book results view 
    # Do you want to search by author
        # book results view
    # Do you want to see your checked out books (include their due dates)

    # Extra Feature (choose subject): WHERE subject = '' ORDER BY RANDOM LIMIT 1
    # Do you want to be recommended a random book?

# Librarian 
    # Assign book to a user:
        # Input: Email
        # Input: ISBN
        # Create the borrow entry (INSERT)

    # Return book from user:
        # Input: Email
        # Input: ISBN
        # Delete the borrow entry (INSERT)
    # View all emails
    # View all books
    # View overdue books and who has them