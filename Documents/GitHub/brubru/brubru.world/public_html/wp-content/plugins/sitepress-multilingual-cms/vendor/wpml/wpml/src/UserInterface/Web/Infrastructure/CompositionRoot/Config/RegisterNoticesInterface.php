<?php

namespace WPML\UserInterface\Web\Infrastructure\CompositionRoot\Config;

interface RegisterNoticesInterface {


  /**
   * @param callable $callback
   * @param array<int, mixed> $args
   *
   * @return void
   */
  public function register( callable $callback, array $args = [] );


}
