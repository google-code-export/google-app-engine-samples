package com.google.appengine.demo.repo;

import javax.jdo.JDOObjectNotFoundException;
import javax.jdo.PersistenceManager;


public class TokenStore {

  public static String getToken(String email) {
    PersistenceManager pm = PMF.get().getPersistenceManager();

    try {
      Token token = pm.getObjectById(Token.class, email);

      return token.getToken();
    } catch (JDOObjectNotFoundException e) {
      return null;
    } finally {
      pm.close();
    }
  }

  public static void addToken(String email, String sessionToken) {
    PersistenceManager pm = PMF.get().getPersistenceManager();

    try {
      Token token = new Token(email, sessionToken);
      pm.makePersistent(token);
    } finally {
      pm.close();
    }
  }
}
