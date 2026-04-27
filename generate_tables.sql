-- Create customers table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

-- Create expenses table
CREATE TABLE IF NOT EXISTS expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'other',
    amount DECIMAL(12,2) NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE NOT NULL
);

-- Insert a sample customer (use this ID in your main.py if needed)
INSERT INTO customers (id, first_name, last_name, email)
VALUES ('6e1a6130-5be4-4778-92a9-b86dc5f16750', 'Test', 'User', 'test@example.com')
ON CONFLICT (email) DO NOTHING;
