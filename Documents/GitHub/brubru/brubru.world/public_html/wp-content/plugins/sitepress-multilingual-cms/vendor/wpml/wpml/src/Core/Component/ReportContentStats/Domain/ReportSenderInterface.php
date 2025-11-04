<?php

namespace WPML\Core\Component\ReportContentStats\Domain;

interface ReportSenderInterface {


  public function send( ContentStatsReport $report ): bool;


}
