-- Copyright 2011 Google Inc. All rights reserved.
-- 
-- MySQL schema for the sql-guestbook sample app. After you've created a Cloud
-- SQL instance, run these statements in your instance's SQL Prompt tab:
-- https://code.google.com/apis/console/

CREATE DATABASE IF NOT EXISTS guestbook;

-- Now select guestbook from the database drop-down next to the Execute button.
-- Or, for a local MySQL database used by the App Engine SDK, run:
-- USE guestbook;

CREATE TABLE IF NOT EXISTS Greetings (
  id INT NOT NULL AUTO_INCREMENT,
  author VARCHAR(32),
  date TIMESTAMP,
  content VARCHAR(512),
  PRIMARY KEY(id),
  KEY(date DESC)
) ENGINE=InnoDB;
