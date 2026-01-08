<?php

namespace WPML\Infrastructure\WordPress\Component\Site\Application\Query;

use WPML\Core\SharedKernel\Component\Site\Application\Query\SiteUrlQueryInterface;

class SiteUrlQuery implements SiteUrlQueryInterface {


  public function get(): string {
    return \get_site_url();
  }


}
