-- From Lab 2: Retail Schema (Fall 2025)

-- Create Customers table
CREATE TABLE Customer (
    CustomerID INTEGER PRIMARY KEY,
    Name TEXT NOT NULL,
    Email TEXT UNIQUE,
    City TEXT
);

CREATE TABLE Orders (
    OrderID INTEGER PRIMARY KEY,
    OrderDate TEXT NOT NULL,         -- store as ISO date string in SQLite
    CustomerID INTEGER,
    TotalAmount REAL,
    FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID)
);

CREATE TABLE Category (
    CategoryID INTEGER PRIMARY KEY,
    CategoryName TEXT
);

CREATE TABLE Product (
    ProductID INTEGER PRIMARY KEY,
    ProductName TEXT NOT NULL,
    CategoryID INTEGER,
    Price REAL,
    FOREIGN KEY (CategoryID) REFERENCES Category(CategoryID)
);

CREATE TABLE OrderDetails (
    OrderDetailID INTEGER PRIMARY KEY,
    OrderID INTEGER,
    ProductID INTEGER,
    Quantity INTEGER,
    FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
    FOREIGN KEY (ProductID) REFERENCES Product(ProductID)
);

-- =========================================
-- INSERT data
-- =========================================

-- Customer
INSERT INTO Customer VALUES (1, 'Alice Johnson', 'alice@email.com', 'Toronto');
INSERT INTO Customer VALUES (2, 'Bob Smith', 'bob@email.com', 'Ottawa');
INSERT INTO Customer VALUES (3, 'Thao Nguyen', 'thao@email.com', 'Ottawa');
INSERT INTO Customer VALUES (4, 'Celine Dion', 'Celine@email.com', 'Montreal');
INSERT INTO Customer VALUES (5, 'The Weekend', 'weekend@email.com', 'Toronto');
INSERT INTO Customer VALUES (6, 'Cold Play', 'cold@email.com', 'Ottawa');
INSERT INTO Customer VALUES (7, 'Micheal Jackson', 'micheal@email.com', 'Vancouver');

-- Category (from distinct Product.Category in LAB2.sql)
INSERT INTO Category (CategoryID, CategoryName) VALUES (1, 'Electronics');
INSERT INTO Category (CategoryID, CategoryName) VALUES (2, 'Office Supply');
INSERT INTO Category (CategoryID, CategoryName) VALUES (3, 'Vehicle');

-- Product (with CategoryID mapped as in LAB2.sql)
INSERT INTO Product VALUES (101, 'Laptop', 1, 1200.00);       -- Electronics
INSERT INTO Product VALUES (102, 'Headphones', 1, 150.00);    -- Electronics
INSERT INTO Product VALUES (103, 'iPhone', 1, 2400.00);       -- Electronics
INSERT INTO Product VALUES (104, 'Pen', 2, 2.00);             -- Office Supply
INSERT INTO Product VALUES (105, 'car', 3, 56000.00);         -- Vehicle
INSERT INTO Product VALUES (106, 'Binder', 2, 3.00);          -- Office Supply

-- Orders (same IDs/dates/amounts as LAB2.sql)
INSERT INTO Orders VALUES (5001, '2025-09-18', 1, 100);
INSERT INTO Orders VALUES (5002, '2025-09-18', 2, 10);
INSERT INTO Orders VALUES (5003, '2025-09-19', 3, 20);
INSERT INTO Orders VALUES (5004, '2025-09-19', 5, 5);
INSERT INTO Orders VALUES (5005, '2025-09-19', 4, 100);
INSERT INTO Orders VALUES (5006, '2025-09-19', 6, 13);
INSERT INTO Orders VALUES (5007, '2025-09-19', 2, 101);
INSERT INTO Orders VALUES (5008, '2025-09-19', 7, 15);
INSERT INTO Orders VALUES (5009, '2025-09-19', 1, 56);
INSERT INTO Orders VALUES (5010, '2025-09-19', 4, 23);
INSERT INTO Orders VALUES (10000, '2025-09-19', 3, 5);

-- OrderDetails (without LineTotal, since you do not have that column here)
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (1, 5001, 101, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (2, 5001, 102, 2);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (3, 5002, 102, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (4, 10000, 102, 5);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (5, 5010, 103, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (6, 5003, 105, 2);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (7, 5004, 104, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (8, 5004, 103, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (9, 5005, 105, 2);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (10, 5006, 104, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (11, 5007, 104, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (12, 5007, 102, 2);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (13, 5007, 101, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (14, 5008, 104, 1);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (15, 5009, 102, 2);
INSERT INTO OrderDetails (OrderDetailID, OrderID, ProductID, Quantity) VALUES (16, 5009, 103, 1);