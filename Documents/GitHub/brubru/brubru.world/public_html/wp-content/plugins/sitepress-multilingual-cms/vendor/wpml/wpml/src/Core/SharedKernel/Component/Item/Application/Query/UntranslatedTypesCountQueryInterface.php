<?php

namespace WPML\Core\SharedKernel\Component\Item\Application\Query;

use WPML\Core\SharedKernel\Component\Item\Application\Query\Dto\UntranslatedTypeCountDto;

interface UntranslatedTypesCountQueryInterface {


  /**
   * @phpstan-param array{
   *    nativeEditorGlobalSetting?: bool,
   *    nativeEditorSettingPerType?: array<string, bool>
   * } $queryData
   *
   * @return UntranslatedTypeCountDto[]
   */
  public function get( array $queryData = [] ): array;


}
