<?php

namespace WPML\Core\SharedKernel\Component\Installer\Application\Query;

interface WpmlActivePluginsQueryInterface {


  /**
   * @return array<int, array{
   *    id: string,
   *    slug: string,
   *    name: string,
   *    active: bool,
   *    current_version: string,
   *   installed_version: string,
   *  }>
   */
  public function getActivePlugins(): array;


}
