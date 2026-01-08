<?php

namespace WPML\Core\Component\ReportContentStats\Domain\Repository;

use WPML\Core\Component\ReportContentStats\Domain\PostTypeStats;

interface PostTypesStatsRepositoryInterface {


  /** @return PostTypeStats[] */
  public function get(): array;


  /** @return void */
  public function update( PostTypeStats $postTypeStats );


  /** @return void */
  public function delete();


}
