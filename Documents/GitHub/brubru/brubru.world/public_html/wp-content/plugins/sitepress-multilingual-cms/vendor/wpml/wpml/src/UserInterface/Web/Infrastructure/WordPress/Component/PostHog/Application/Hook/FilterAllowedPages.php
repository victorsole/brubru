<?php

namespace WPML\UserInterface\Web\Infrastructure\WordPress\Component\PostHog\Application\Hook;

use WPML\Core\SharedKernel\Component\PostHog\Application\Hook\FilterAllowedPagesInterface;

class FilterAllowedPages implements FilterAllowedPagesInterface {


  /**
   * @param string[] $allowedPages
   *
   * @return string[]
   */
  public function filter( array $allowedPages ): array {
    return apply_filters( 'wpml_posthog_allowed_pages', $allowedPages );
  }


}
