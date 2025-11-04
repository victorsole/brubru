<?php

namespace WPML\UserInterface\Web\Infrastructure\WordPress\CompositionRoot\Config;

use WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config\RegisterNoticesInterface;

class RegisterNotices implements RegisterNoticesInterface {


  /**
   * @param callable $callback
   * @param array<int, mixed> $args
   *
   * @return void
   */
  public function register( callable $callback, array $args = [] ) {
    // Use `all_admin_notices` as `admin_notices` are removed from TM dashboard to keep it clean.
    add_action(
      'all_admin_notices',
      function () use ( $callback, $args ) {
        call_user_func_array( $callback, $args );
      }
    );
  }


}
