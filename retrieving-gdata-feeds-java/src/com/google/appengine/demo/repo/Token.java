package com.google.appengine.demo.repo;

import javax.jdo.annotations.PersistenceCapable;
import javax.jdo.annotations.Persistent;
import javax.jdo.annotations.PrimaryKey;

@PersistenceCapable
public class Token {

  @PrimaryKey
  private String email;

  @Persistent
  private String token;

  public Token(String email, String token) {
    this.email = email;
    this.token = token;
  }

  public String getEmail() {
    return email;
  }

  public String getToken() {
    return token;
  }
}
