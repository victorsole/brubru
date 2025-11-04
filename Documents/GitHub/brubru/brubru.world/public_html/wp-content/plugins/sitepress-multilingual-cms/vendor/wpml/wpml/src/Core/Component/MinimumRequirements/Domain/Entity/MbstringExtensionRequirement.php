<?php

namespace WPML\Core\Component\MinimumRequirements\Domain\Entity;

use WPML\Core\SharedKernel\Component\Server\Domain\ServerInfoInterface;

class MbstringExtensionRequirement extends RequirementBase {
  const EXTENSION_NAME = 'mbstring';

  /** @var ServerInfoInterface */
  private $serverInfo;


  /**
   * Constructor.
   *
   * @param ServerInfoInterface $serverInfo The server info service.
   */
  public function __construct( ServerInfoInterface $serverInfo ) {
    $this->serverInfo = $serverInfo;
  }


  public function getId(): int {
    return 7;
  }


  public function getTitle(): string {
    return __( 'Multibyte String Extension', 'wpml' );
  }


  public function getMessages(): array {
    return [
      [
        'type'    => 'p',
        'message' => sprintf(
          __(
            'The %sMultibyte String extension%s is required to handle non-Latin character sets in WPML.',
            'wpml'
          ),
          '<a href="https://www.php.net/manual/en/book.mbstring.php" target="_blank">',
          '</a>'
        ),
      ],
      [
        'type'    => 'alert',
        'message' => __(
          'Contact your hosting provider to install the Multibyte String (mbstring) PHP extension.',
          'wpml'
        ),
      ]
    ];
  }


  protected function doIsValid(): bool {
    return $this->serverInfo->isExtensionLoaded( self::EXTENSION_NAME );
  }


  protected function getRequirementType(): string {
    return 'MBSTRING_EXTENSION';
  }


}
