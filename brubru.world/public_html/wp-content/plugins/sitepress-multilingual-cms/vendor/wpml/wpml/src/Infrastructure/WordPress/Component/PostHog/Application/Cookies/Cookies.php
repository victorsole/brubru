<?php

namespace WPML\Infrastructure\WordPress\Component\PostHog\Application\Cookies;

use WPML\Core\Component\PostHog\Application\Cookies\CookiesInterface;

class Cookies implements CookiesInterface {

  const DISTINCT_ID_COOKIE_NAME = 'wpml_ph_distinct_id';
  const SESSION_ID_COOKIE_NAME = 'wpml_ph_session_id';


  /**
   * @return string|false
   */
  public function getDistinctId() {
    return $_COOKIE[ self::DISTINCT_ID_COOKIE_NAME ] ?? false;
  }


  /**
   * @return string|false
   */
  public function getSessionId() {
    return $_COOKIE[ self::SESSION_ID_COOKIE_NAME ] ?? false;
  }


}
