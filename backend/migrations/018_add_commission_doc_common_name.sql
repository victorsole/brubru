-- Migration 018: Add common_name to commission_documents
-- Colloquial/short name for documents (e.g. "Digital Omnibus Act")
-- Used by AI context builder to help chatbot connect user queries to formal documents

ALTER TABLE commission_documents ADD COLUMN IF NOT EXISTS common_name VARCHAR;
