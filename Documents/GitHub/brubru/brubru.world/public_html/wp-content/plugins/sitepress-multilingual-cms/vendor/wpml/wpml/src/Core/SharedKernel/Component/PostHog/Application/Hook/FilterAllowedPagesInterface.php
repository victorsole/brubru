<?php

namespace WPML\Core\SharedKernel\Component\PostHog\Application\Hook;

interface FilterAllowedPagesInterface {


  /**
   * @param string[] $allowedPages
   *
   * @return string[]
   */
  public function filter( array $allowedPages ): array;


}
