-- Complete SQLite-compatible schema with sample data

-- Create Students table
CREATE TABLE IF NOT EXISTS Students (
    StudentID INTEGER PRIMARY KEY AUTOINCREMENT,
    FirstName TEXT NOT NULL,
    LastName TEXT NOT NULL,
    Age INTEGER CHECK(Age >= 16 AND Age <= 100),
    Major TEXT
);

-- Create Courses table  
CREATE TABLE IF NOT EXISTS Courses (
    CourseID INTEGER PRIMARY KEY AUTOINCREMENT,
    CourseName TEXT NOT NULL,
    Credits INTEGER CHECK(Credits > 0 AND Credits <= 6)
);

-- Create Enrollments table (junction table)
CREATE TABLE IF NOT EXISTS Enrollments (
    EnrollmentID INTEGER PRIMARY KEY AUTOINCREMENT,
    StudentID INTEGER NOT NULL,
    CourseID INTEGER NOT NULL,
    Grade TEXT CHECK(Grade IN ('A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'D', 'F')),
    FOREIGN KEY(StudentID) REFERENCES Students(StudentID) ON DELETE CASCADE,
    FOREIGN KEY(CourseID) REFERENCES Courses(CourseID) ON DELETE CASCADE,
    UNIQUE(StudentID, CourseID)  -- Prevent duplicate enrollments
);

-- Insert sample Students
INSERT OR REPLACE INTO Students (StudentID, FirstName, LastName, Age, Major) VALUES
(1, 'Alice', 'Johnson', 20, 'Computer Science'),
(2, 'Bob', 'Smith', 22, 'Business'),
(3, 'Clara', 'Brown', 19, 'Data Analytics');

-- Insert sample Courses
INSERT OR REPLACE INTO Courses (CourseID, CourseName, Credits) VALUES
(1, 'Database Systems', 3),
(2, 'Business Intelligence', 4),
(3, 'Python Programming', 3);

-- Insert Enrollments
INSERT OR IGNORE INTO Enrollments (EnrollmentID, StudentID, CourseID, Grade) VALUES
(1, 1, 1, 'A'),
(2, 1, 2, 'B'),
(3, 2, 3, 'A'),
(4, 3, 1, 'B');