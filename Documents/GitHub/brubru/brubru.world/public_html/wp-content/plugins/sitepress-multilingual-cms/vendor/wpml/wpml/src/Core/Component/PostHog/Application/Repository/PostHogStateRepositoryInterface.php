<?php

namespace WPML\Core\Component\PostHog\Application\Repository;

interface PostHogStateRepositoryInterface {


  public function isEnabled(): bool;


  /**
   * @return void
   */
  public function setIsEnabled( bool $isEnabled );


}
