<?php
/**
 * Plugin Name:       Abhinav Group AI Chatbot
 * Plugin URI:        https://abhinavgroup.co.in/
 * Description:       AI-powered property sales chatbot for Abhinav Group. Loads a floating chat widget that connects to the Abhinav Group chatbot API.
 * Version:           1.0.0
 * Requires at least: 5.6
 * Requires PHP:      7.4
 * Author:            Abhinav Group Technology Team
 * Author URI:        https://abhinavgroup.co.in/
 * License:           Proprietary
 * Text Domain:       abhinav-chatbot
 *
 * IMPORTANT:
 * - This plugin does NOT modify any existing WordPress functionality.
 * - It does NOT interfere with the existing WhatsApp integration.
 * - It can be safely deactivated without breaking any other feature.
 * - All chatbot API credentials are stored in WordPress options (not hardcoded).
 *
 * To remove: Deactivate and delete this plugin. No database cleanup needed.
 */

// Prevent direct access
if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

// Plugin version and option key constants
define( 'ABHINAV_CHATBOT_VERSION', '1.0.0' );
define( 'ABHINAV_CHATBOT_OPTION_KEY', 'abhinav_chatbot_settings' );
define( 'ABHINAV_CHATBOT_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'ABHINAV_CHATBOT_PLUGIN_URL', plugin_dir_url( __FILE__ ) );


/**
 * ── Core class ──────────────────────────────────────────────────────────────
 */
class Abhinav_Chatbot_Plugin {

    private static $instance = null;

    public static function get_instance(): self {
        if ( null === self::$instance ) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action( 'init',            [ $this, 'load_textdomain' ] );
        add_action( 'wp_enqueue_scripts', [ $this, 'enqueue_widget' ] );
        add_action( 'admin_menu',      [ $this, 'add_admin_menu' ] );
        add_action( 'admin_init',      [ $this, 'register_settings' ] );
        add_action( 'admin_enqueue_scripts', [ $this, 'enqueue_admin_scripts' ] );
        add_filter( 'plugin_action_links_' . plugin_basename( __FILE__ ), [ $this, 'add_action_links' ] );
    }

    // ── Localisation ──────────────────────────────────────────────────────

    public function load_textdomain(): void {
        load_plugin_textdomain(
            'abhinav-chatbot',
            false,
            dirname( plugin_basename( __FILE__ ) ) . '/languages'
        );
    }

    // ── Frontend Widget ───────────────────────────────────────────────────

    public function enqueue_widget(): void {
        $settings = $this->get_settings();

        // Do not load if disabled
        if ( empty( $settings['enabled'] ) || ! $settings['enabled'] ) {
            return;
        }

        // Do not load if no API base URL configured
        if ( empty( $settings['api_base'] ) ) {
            return;
        }

        // Check page exclusions
        if ( $this->is_excluded_page( $settings ) ) {
            return;
        }

        // Enqueue the minified widget JS (falls back to src if dist not built yet)
        $js_file = 'dist/abhinav-chatbot.min.js';
        if ( ! file_exists( ABHINAV_CHATBOT_PLUGIN_DIR . $js_file ) ) {
            $js_file = 'assets/widget.js';
        }

        wp_enqueue_script(
            'abhinav-chatbot-widget',
            ABHINAV_CHATBOT_PLUGIN_URL . $js_file,
            [],   // No dependencies — fully self-contained
            ABHINAV_CHATBOT_VERSION,
            true  // Load in footer — does not block page rendering
        );

        // Pass configuration to the widget via inline script
        // NOTE: Never expose secret keys here — widget key is a read-only public key
        $config = [
            'apiBase'    => esc_url_raw( $settings['api_base'] ),
            'widgetKey'  => sanitize_text_field( $settings['widget_key'] ?? '' ),
            'sourcePage' => esc_url_raw( get_permalink() ?: home_url( $_SERVER['REQUEST_URI'] ?? '/' ) ),
            'lang'       => sanitize_text_field( $settings['language'] ?? 'auto' ),
            'position'   => in_array( $settings['position'] ?? '', [ 'bottom-right', 'bottom-left' ], true )
                           ? $settings['position']
                           : 'bottom-right',
            'autoOpen'   => ! empty( $settings['auto_open'] ),
            'autoOpenDelay' => absint( $settings['auto_open_delay'] ?? 3000 ),
        ];

        wp_add_inline_script(
            'abhinav-chatbot-widget',
            'window.AbhinavChatConfig = ' . wp_json_encode( $config ) . ';',
            'before'
        );
    }

    private function is_excluded_page( array $settings ): bool {
        $excluded_ids = array_filter( array_map( 'intval',
            explode( ',', $settings['exclude_pages'] ?? '' )
        ) );
        if ( ! empty( $excluded_ids ) && is_page( $excluded_ids ) ) {
            return true;
        }
        // Always exclude admin pages (should not appear anyway, but be safe)
        if ( is_admin() ) {
            return true;
        }
        return false;
    }

    // ── Admin Menu ────────────────────────────────────────────────────────

    public function add_admin_menu(): void {
        add_options_page(
            __( 'Abhinav Chatbot Settings', 'abhinav-chatbot' ),
            __( 'Abhinav Chatbot', 'abhinav-chatbot' ),
            'manage_options',
            'abhinav-chatbot',
            [ $this, 'render_settings_page' ]
        );
    }

    public function enqueue_admin_scripts( string $hook ): void {
        if ( 'settings_page_abhinav-chatbot' !== $hook ) {
            return;
        }
        // Minimal inline styles for the settings page
        wp_add_inline_style( 'wp-admin', '
            .abhinav-chatbot-settings .form-table th { width: 220px; }
            .abhinav-chatbot-settings .notice-box { background:#f0f7ff; border-left:4px solid #0073aa; padding:12px 16px; margin:16px 0; border-radius:4px; }
            .abhinav-chatbot-settings .status-badge { display:inline-block; padding:3px 10px; border-radius:12px; font-size:12px; font-weight:600; }
            .abhinav-chatbot-settings .status-badge.ok { background:#d4edda; color:#155724; }
            .abhinav-chatbot-settings .status-badge.warn { background:#fff3cd; color:#856404; }
        ' );
    }

    // ── Settings Registration ─────────────────────────────────────────────

    public function register_settings(): void {
        register_setting(
            'abhinav_chatbot_group',
            ABHINAV_CHATBOT_OPTION_KEY,
            [
                'type'              => 'array',
                'sanitize_callback' => [ $this, 'sanitize_settings' ],
            ]
        );

        add_settings_section(
            'abhinav_chatbot_main',
            __( 'API Connection', 'abhinav-chatbot' ),
            [ $this, 'render_section_main' ],
            'abhinav-chatbot'
        );

        add_settings_section(
            'abhinav_chatbot_display',
            __( 'Widget Display', 'abhinav-chatbot' ),
            null,
            'abhinav-chatbot'
        );

        $fields = [
            [ 'enabled',         'abhinav_chatbot_main',    __( 'Enable Chatbot', 'abhinav-chatbot' ),        'render_field_enabled' ],
            [ 'api_base',        'abhinav_chatbot_main',    __( 'API Base URL', 'abhinav-chatbot' ),           'render_field_api_base' ],
            [ 'widget_key',      'abhinav_chatbot_main',    __( 'Widget API Key', 'abhinav-chatbot' ),         'render_field_widget_key' ],
            [ 'language',        'abhinav_chatbot_display', __( 'Language', 'abhinav-chatbot' ),               'render_field_language' ],
            [ 'position',        'abhinav_chatbot_display', __( 'Widget Position', 'abhinav-chatbot' ),        'render_field_position' ],
            [ 'auto_open',       'abhinav_chatbot_display', __( 'Auto-open Chat', 'abhinav-chatbot' ),         'render_field_auto_open' ],
            [ 'auto_open_delay', 'abhinav_chatbot_display', __( 'Auto-open Delay (ms)', 'abhinav-chatbot' ),   'render_field_auto_open_delay' ],
            [ 'exclude_pages',   'abhinav_chatbot_display', __( 'Exclude Page IDs', 'abhinav-chatbot' ),       'render_field_exclude_pages' ],
        ];

        foreach ( $fields as [ $id, $section, $label, $callback ] ) {
            add_settings_field( $id, $label, [ $this, $callback ], 'abhinav-chatbot', $section );
        }
    }

    public function sanitize_settings( $input ): array {
        $clean = [];
        $clean['enabled']         = ! empty( $input['enabled'] );
        $clean['api_base']        = esc_url_raw( trim( $input['api_base'] ?? '' ) );
        $clean['widget_key']      = sanitize_text_field( $input['widget_key'] ?? '' );
        $clean['language']        = in_array( $input['language'] ?? 'auto', [ 'auto', 'en', 'hi' ], true )
                                  ? $input['language']
                                  : 'auto';
        $clean['position']        = in_array( $input['position'] ?? '', [ 'bottom-right', 'bottom-left' ], true )
                                  ? $input['position']
                                  : 'bottom-right';
        $clean['auto_open']       = ! empty( $input['auto_open'] );
        $clean['auto_open_delay'] = absint( $input['auto_open_delay'] ?? 3000 );
        $clean['exclude_pages']   = sanitize_text_field( $input['exclude_pages'] ?? '' );
        return $clean;
    }

    // ── Settings Page Render ──────────────────────────────────────────────

    public function render_settings_page(): void {
        if ( ! current_user_can( 'manage_options' ) ) {
            wp_die( __( 'You do not have permission to access this page.', 'abhinav-chatbot' ) );
        }
        $settings = $this->get_settings();
        $api_ok   = ! empty( $settings['api_base'] );
        ?>
        <div class="wrap abhinav-chatbot-settings">
            <h1>
                <span style="color:#1a2f5a;">&#127968;</span>
                <?php esc_html_e( 'Abhinav Group AI Chatbot Settings', 'abhinav-chatbot' ); ?>
            </h1>

            <div class="notice-box">
                <strong><?php esc_html_e( 'Status:', 'abhinav-chatbot' ); ?></strong>
                <?php if ( $settings['enabled'] && $api_ok ) : ?>
                    <span class="status-badge ok"><?php esc_html_e( 'Active', 'abhinav-chatbot' ); ?></span>
                    <?php esc_html_e( ' — Chatbot widget is live on all pages.', 'abhinav-chatbot' ); ?>
                <?php elseif ( ! $settings['enabled'] ) : ?>
                    <span class="status-badge warn"><?php esc_html_e( 'Disabled', 'abhinav-chatbot' ); ?></span>
                    <?php esc_html_e( ' — Enable the chatbot below to activate.', 'abhinav-chatbot' ); ?>
                <?php else : ?>
                    <span class="status-badge warn"><?php esc_html_e( 'Missing API URL', 'abhinav-chatbot' ); ?></span>
                    <?php esc_html_e( ' — Enter the backend API URL below.', 'abhinav-chatbot' ); ?>
                <?php endif; ?>
            </div>

            <form method="post" action="options.php">
                <?php
                settings_fields( 'abhinav_chatbot_group' );
                do_settings_sections( 'abhinav-chatbot' );
                submit_button( __( 'Save Settings', 'abhinav-chatbot' ) );
                ?>
            </form>

            <hr>
            <h2><?php esc_html_e( 'Plugin Information', 'abhinav-chatbot' ); ?></h2>
            <table class="form-table">
                <tr>
                    <th><?php esc_html_e( 'Plugin Version', 'abhinav-chatbot' ); ?></th>
                    <td><code><?php echo esc_html( ABHINAV_CHATBOT_VERSION ); ?></code></td>
                </tr>
                <tr>
                    <th><?php esc_html_e( 'Widget File', 'abhinav-chatbot' ); ?></th>
                    <td>
                        <?php
                        $dist = ABHINAV_CHATBOT_PLUGIN_DIR . 'dist/abhinav-chatbot.min.js';
                        $src  = ABHINAV_CHATBOT_PLUGIN_DIR . 'assets/widget.js';
                        if ( file_exists( $dist ) ) {
                            echo '<span class="status-badge ok">dist/abhinav-chatbot.min.js</span> ' . esc_html__( '(minified)', 'abhinav-chatbot' );
                        } elseif ( file_exists( $src ) ) {
                            echo '<span class="status-badge warn">assets/widget.js</span> ' . esc_html__( '(development — run build to minify)', 'abhinav-chatbot' );
                        } else {
                            echo '<span class="status-badge warn">' . esc_html__( 'Widget file not found — please upload widget.js to the assets/ folder.', 'abhinav-chatbot' ) . '</span>';
                        }
                        ?>
                    </td>
                </tr>
                <tr>
                    <th><?php esc_html_e( 'WhatsApp Integration', 'abhinav-chatbot' ); ?></th>
                    <td><span class="status-badge ok"><?php esc_html_e( 'Not modified', 'abhinav-chatbot' ); ?></span>
                    <?php esc_html_e( ' — This plugin does not touch any existing WhatsApp integration.', 'abhinav-chatbot' ); ?>
                    </td>
                </tr>
            </table>
        </div>
        <?php
    }

    public function render_section_main(): void {
        echo '<p>' . esc_html__( 'Configure the connection to the Abhinav Group chatbot backend API.', 'abhinav-chatbot' ) . '</p>';
    }

    // ── Individual Field Renderers ─────────────────────────────────────────

    private function get_settings(): array {
        $defaults = [
            'enabled'         => false,
            'api_base'        => '',
            'widget_key'      => '',
            'language'        => 'auto',
            'position'        => 'bottom-right',
            'auto_open'       => false,
            'auto_open_delay' => 3000,
            'exclude_pages'   => '',
        ];
        $saved = get_option( ABHINAV_CHATBOT_OPTION_KEY, [] );
        return wp_parse_args( $saved, $defaults );
    }

    public function render_field_enabled(): void {
        $s = $this->get_settings();
        ?>
        <label>
            <input type="checkbox" name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[enabled]"
                   value="1" <?php checked( $s['enabled'] ); ?>>
            <?php esc_html_e( 'Enable chatbot widget on all pages', 'abhinav-chatbot' ); ?>
        </label>
        <?php
    }

    public function render_field_api_base(): void {
        $s = $this->get_settings();
        ?>
        <input type="url" name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[api_base]"
               value="<?php echo esc_attr( $s['api_base'] ); ?>"
               class="regular-text" placeholder="https://api.abhinavgroup.co.in">
        <p class="description">
            <?php esc_html_e( 'The base URL of the Abhinav Group chatbot backend API server.', 'abhinav-chatbot' ); ?>
            <?php esc_html_e( 'Example: https://api.abhinavgroup.co.in (no trailing slash).', 'abhinav-chatbot' ); ?>
        </p>
        <?php
    }

    public function render_field_widget_key(): void {
        $s = $this->get_settings();
        ?>
        <input type="text" name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[widget_key]"
               value="<?php echo esc_attr( $s['widget_key'] ); ?>"
               class="regular-text" placeholder="wk_xxxxxxxxxxxx">
        <p class="description">
            <?php esc_html_e( 'Public widget API key (read-only). Never enter admin or secret keys here.', 'abhinav-chatbot' ); ?>
        </p>
        <?php
    }

    public function render_field_language(): void {
        $s = $this->get_settings();
        $options = [ 'auto' => 'Auto-detect (recommended)', 'en' => 'English only', 'hi' => 'Hindi only' ];
        ?>
        <select name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[language]">
            <?php foreach ( $options as $val => $label ) : ?>
                <option value="<?php echo esc_attr( $val ); ?>" <?php selected( $s['language'], $val ); ?>>
                    <?php echo esc_html( $label ); ?>
                </option>
            <?php endforeach; ?>
        </select>
        <?php
    }

    public function render_field_position(): void {
        $s = $this->get_settings();
        ?>
        <select name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[position]">
            <option value="bottom-right" <?php selected( $s['position'], 'bottom-right' ); ?>>
                <?php esc_html_e( 'Bottom Right (recommended)', 'abhinav-chatbot' ); ?>
            </option>
            <option value="bottom-left" <?php selected( $s['position'], 'bottom-left' ); ?>>
                <?php esc_html_e( 'Bottom Left', 'abhinav-chatbot' ); ?>
            </option>
        </select>
        <?php
    }

    public function render_field_auto_open(): void {
        $s = $this->get_settings();
        ?>
        <label>
            <input type="checkbox" name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[auto_open]"
                   value="1" <?php checked( $s['auto_open'] ); ?>>
            <?php esc_html_e( 'Automatically open chat after delay', 'abhinav-chatbot' ); ?>
        </label>
        <?php
    }

    public function render_field_auto_open_delay(): void {
        $s = $this->get_settings();
        ?>
        <input type="number" name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[auto_open_delay]"
               value="<?php echo esc_attr( $s['auto_open_delay'] ); ?>"
               min="1000" max="30000" step="500" class="small-text">
        <span><?php esc_html_e( 'milliseconds (3000 = 3 seconds)', 'abhinav-chatbot' ); ?></span>
        <?php
    }

    public function render_field_exclude_pages(): void {
        $s = $this->get_settings();
        ?>
        <input type="text" name="<?php echo esc_attr( ABHINAV_CHATBOT_OPTION_KEY ); ?>[exclude_pages]"
               value="<?php echo esc_attr( $s['exclude_pages'] ); ?>"
               class="regular-text" placeholder="12, 45, 78">
        <p class="description">
            <?php esc_html_e( 'Comma-separated WordPress page IDs where the chatbot should NOT appear. Leave blank to show on all pages.', 'abhinav-chatbot' ); ?>
        </p>
        <?php
    }

    // ── Plugin action links ───────────────────────────────────────────────

    public function add_action_links( array $links ): array {
        $settings_link = '<a href="' . admin_url( 'options-general.php?page=abhinav-chatbot' ) . '">'
                       . __( 'Settings', 'abhinav-chatbot' ) . '</a>';
        array_unshift( $links, $settings_link );
        return $links;
    }
}


/**
 * ── Activation / Deactivation Hooks ─────────────────────────────────────────
 */
function abhinav_chatbot_activate(): void {
    // Set sensible defaults on first activation
    if ( false === get_option( ABHINAV_CHATBOT_OPTION_KEY ) ) {
        update_option( ABHINAV_CHATBOT_OPTION_KEY, [
            'enabled'         => false,  // Disabled until admin configures API URL
            'api_base'        => '',
            'widget_key'      => '',
            'language'        => 'auto',
            'position'        => 'bottom-right',
            'auto_open'       => false,
            'auto_open_delay' => 3000,
            'exclude_pages'   => '',
        ] );
    }
}
register_activation_hook( __FILE__, 'abhinav_chatbot_activate' );

function abhinav_chatbot_deactivate(): void {
    // Nothing to clean up on deactivate — settings are preserved for re-activation
}
register_deactivation_hook( __FILE__, 'abhinav_chatbot_deactivate' );

function abhinav_chatbot_uninstall(): void {
    // Clean up settings on full uninstall
    delete_option( ABHINAV_CHATBOT_OPTION_KEY );
}
register_uninstall_hook( __FILE__, 'abhinav_chatbot_uninstall' );


/**
 * ── Bootstrap ────────────────────────────────────────────────────────────────
 */
add_action( 'plugins_loaded', function () {
    Abhinav_Chatbot_Plugin::get_instance();
} );
