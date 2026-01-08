<?php

namespace WPML\Core\Component\PostHog\Application\Cookies;

interface CookiesInterface {


  /**
   * @return string|false
   */
  public function getDistinctId();


  /**
   * @return string|false
   */
  public function getSessionId();


}
