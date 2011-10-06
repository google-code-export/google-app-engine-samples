-- Copyright 2011 Google Inc. All rights reserved.
-- 
-- MySQL schema for the sql-shell sample app. After you've created a Cloud
-- SQL instance, run these statements in your instance's SQL Prompt tab:
-- https://code.google.com/apis/console/

CREATE DATABASE IF NOT EXISTS shell;

-- Now select shell from the database drop-down next to the Execute button.
-- Or, for a local MySQL database used by the App Engine SDK, run:
-- USE shell;

CREATE TABLE IF NOT EXISTS Foo (
  id INT NOT NULL AUTO_INCREMENT,
  bar VARCHAR(512),
  PRIMARY KEY(id)
) ENGINE=InnoDB;
