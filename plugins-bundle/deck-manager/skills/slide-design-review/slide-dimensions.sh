#!/usr/bin/env bash
# Slide dimension calculator using the golden ratio.
# Computes optimal spacing, font sizes, and positions for slide layouts.
#
# Usage:
#   ./scripts/slide-dimensions.sh                    # Full analysis for 1920x1080
#   ./scripts/slide-dimensions.sh --canvas WxH       # Custom canvas (e.g., 1280x720)
#   ./scripts/slide-dimensions.sh --title-size 96     # Compute hierarchy from title size
#   ./scripts/slide-dimensions.sh --audit             # Audit current layout.ts values

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Golden ratio
PHI="1.618"

# Defaults
CANVAS_W=1920
CANVAS_H=1080
TITLE_SIZE=""
AUDIT=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --canvas)
            CANVAS_W="${2%%x*}"
            CANVAS_H="${2##*x}"
            shift 2
            ;;
        --title-size)
            TITLE_SIZE="$2"
            shift 2
            ;;
        --audit)
            AUDIT=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${CYAN}━━━ Slide Dimension Calculator ━━━${NC}"
echo -e "Canvas: ${BOLD}${CANVAS_W}×${CANVAS_H}${NC}"
echo -e "Golden Ratio (φ): ${BOLD}${PHI}${NC}"
echo ""

# --- Golden section lines ---
echo -e "${CYAN}▸ Golden Section Lines${NC}"
GS_Y=$(echo "$CANVAS_H / $PHI" | bc)
GS_Y_INV=$(echo "$CANVAS_H - $GS_Y" | bc)
GS_X=$(echo "$CANVAS_W / $PHI" | bc)
echo -e "  Horizontal: ${GREEN}y = ${GS_Y}px${NC} from top (${GS_Y_INV}px from bottom)"
echo -e "  Vertical:   ${GREEN}x = ${GS_X}px${NC} from left"
echo -e "  ${DIM}Place primary focal elements at or above y=${GS_Y}${NC}"
echo ""

# --- Optical center ---
echo -e "${CYAN}▸ Optical Center${NC}"
OC_Y=$(echo "$CANVAS_H * 0.382" | bc)  # 1 - 1/φ
OC_X=$(echo "$CANVAS_W / 2" | bc)
echo -e "  Position: ${GREEN}(${OC_X}, ${OC_Y})${NC}"
echo -e "  ${DIM}Title slides: place hero text center at y≈${OC_Y}${NC}"
echo ""

# --- Margins (golden ratio based) ---
echo -e "${CYAN}▸ Recommended Margins${NC}"
# Side margins = canvas_w / (2 * φ^3) ≈ 5.6% of width
MARGIN_SIDE=$(echo "$CANVAS_W / (2 * $PHI * $PHI * $PHI)" | bc)
# Top margin = side / φ
MARGIN_TOP=$(echo "$MARGIN_SIDE / $PHI" | bc)
echo -e "  Side margins:   ${GREEN}${MARGIN_SIDE}px${NC} (${DIM}≈$(echo "scale=1; $MARGIN_SIDE * 100 / $CANVAS_W" | bc)% of width${NC})"
echo -e "  Top margin:     ${GREEN}${MARGIN_TOP}px${NC}"
echo -e "  Bottom margin:  ${GREEN}${MARGIN_TOP}px${NC}"
echo ""

# --- Rule of thirds grid ---
echo -e "${CYAN}▸ Rule of Thirds Grid${NC}"
THIRD_X1=$(echo "$CANVAS_W / 3" | bc)
THIRD_X2=$(echo "$CANVAS_W * 2 / 3" | bc)
THIRD_Y1=$(echo "$CANVAS_H / 3" | bc)
THIRD_Y2=$(echo "$CANVAS_H * 2 / 3" | bc)
echo -e "  Vertical lines:   x = ${GREEN}${THIRD_X1}${NC}, ${GREEN}${THIRD_X2}${NC}"
echo -e "  Horizontal lines: y = ${GREEN}${THIRD_Y1}${NC}, ${GREEN}${THIRD_Y2}${NC}"
echo -e "  ${DIM}Power points (intersections): (${THIRD_X1},${THIRD_Y1}) (${THIRD_X2},${THIRD_Y1}) (${THIRD_X1},${THIRD_Y2}) (${THIRD_X2},${THIRD_Y2})${NC}"
echo ""

# --- Font size hierarchy ---
echo -e "${CYAN}▸ Font Size Hierarchy (Golden Ratio)${NC}"
if [ -n "$TITLE_SIZE" ]; then
    BASE="$TITLE_SIZE"
else
    # Default: hero title = canvas_h / 11 (≈98pt for 1080)
    BASE=$(echo "$CANVAS_H / 11" | bc)
fi
S1=$BASE
S2=$(echo "scale=0; $S1 / $PHI" | bc)
S3=$(echo "scale=0; $S2 / $PHI" | bc)
S4=$(echo "scale=0; $S3 / $PHI" | bc)
S5=$(echo "scale=0; $S4 / $PHI" | bc)
echo -e "  Hero title:    ${GREEN}${S1}pt${NC}"
echo -e "  Slide title:   ${GREEN}${S2}pt${NC}  (hero / φ)"
echo -e "  Subtitle/Lead: ${GREEN}${S3}pt${NC}  (title / φ)"
echo -e "  Body/Bullets:  ${GREEN}${S4}pt${NC}  (subtitle / φ)"
echo -e "  Caption/Footer:${GREEN}${S5}pt${NC}  (body / φ)"
echo ""

# --- Metric card dimensions ---
echo -e "${CYAN}▸ Metric Card Suggestions${NC}"
# 2×2 grid with golden ratio card proportions
CARD_AREA_W=$(echo "$CANVAS_W - 2 * $MARGIN_SIDE" | bc)
CARD_AREA_H=$(echo "$CANVAS_H * 0.6" | bc)  # 60% of slide for cards
CARD_GAP=30
CARD_W_CALC=$(echo "($CARD_AREA_W - $CARD_GAP) / 2" | bc)
CARD_H_CALC=$(echo "($CARD_AREA_H - $CARD_GAP) / 2" | bc)
echo -e "  Available area: ${CARD_AREA_W}×${CARD_AREA_H}px"
echo -e "  Card size:      ${GREEN}${CARD_W_CALC}×${CARD_H_CALC}px${NC} (with ${CARD_GAP}px gap)"
echo -e "  Card ratio:     $(echo "scale=2; $CARD_W_CALC / $CARD_H_CALC" | bc):1"
echo ""

# --- Spacing suggestions ---
echo -e "${CYAN}▸ Spacing Suggestions${NC}"
TITLE_TO_CONTENT=$(echo "scale=0; $S1 * $PHI" | bc)
BULLET_SPACING=$(echo "scale=0; $S4 * 2.5" | bc)
echo -e "  Title → first content: ${GREEN}${TITLE_TO_CONTENT}px${NC}  (hero_size × φ)"
echo -e "  Between bullets:       ${GREEN}${BULLET_SPACING}px${NC}  (bullet_size × 2.5)"
echo -e "  Content → footer:      ${GREEN}$(echo "scale=0; $CANVAS_H * 0.08" | bc)px${NC}  (8% of height)"
echo ""

# --- Readability checks ---
echo -e "${CYAN}▸ Readability at Distance (1920×1080 → 55\" screen)${NC}"
MIN_TEXT_PCT=3   # 3% of slide height = minimum readable size
MIN_TEXT_PX=$(echo "$CANVAS_H * $MIN_TEXT_PCT / 100" | bc)
MIN_TEXT_PT=$(echo "scale=0; $MIN_TEXT_PX * 72 / 96" | bc)  # px to pt (96 DPI)
echo -e "  Minimum readable text: ${GREEN}${MIN_TEXT_PT}pt${NC} (${MIN_TEXT_PX}px = ${MIN_TEXT_PCT}% of ${CANVAS_H}px)"
echo -e "  10-foot rule (titles): ${GREEN}$(echo "scale=0; $CANVAS_H * 5 / 100 * 72 / 96" | bc)pt${NC} minimum"
echo -e "  20-foot rule (body):   ${GREEN}${MIN_TEXT_PT}pt${NC} minimum"
echo ""

# --- Fill factor check ---
echo -e "${CYAN}▸ Content Fill Factor${NC}"
echo -e "  Target: content should fill ${GREEN}40-65%${NC} of slide height"
echo -e "  40% of ${CANVAS_H}px = ${GREEN}$(echo "$CANVAS_H * 40 / 100" | bc)px${NC} minimum content block"
echo -e "  65% of ${CANVAS_H}px = ${GREEN}$(echo "$CANVAS_H * 65 / 100" | bc)px${NC} maximum content block"
echo ""

if [ "$AUDIT" = true ]; then
    # Calculate fill factor for a typical 4-bullet content slide
    CURRENT_TITLE=$(echo "scale=0; $S2" | bc)
    CURRENT_BULLET=$(echo "scale=0; $S4" | bc)
    BULLET_COUNT=4
    TITLE_GAP=40
    BULLET_GAP=$(echo "scale=0; $CURRENT_BULLET * 2.5" | bc)
    CONTENT_HEIGHT=$(echo "$CURRENT_TITLE + $TITLE_GAP + ($CURRENT_BULLET + $BULLET_GAP) * $BULLET_COUNT" | bc)
    FILL_PCT=$(echo "scale=1; $CONTENT_HEIGHT * 100 / $CANVAS_H" | bc)
    echo -e "${CYAN}▸ Estimated Fill Factor (4 bullets)${NC}"
    echo -e "  Content height: ${CONTENT_HEIGHT}px / ${CANVAS_H}px = ${BOLD}${FILL_PCT}%${NC}"
    if [ "$(echo "$FILL_PCT < 40" | bc)" -eq 1 ]; then
        echo -e "  ${YELLOW}⚠  Below 40% — content will look sparse. Increase font sizes or spacing.${NC}"
    elif [ "$(echo "$FILL_PCT > 65" | bc)" -eq 1 ]; then
        echo -e "  ${YELLOW}⚠  Above 65% — content may feel cramped. Reduce font sizes or spacing.${NC}"
    else
        echo -e "  ${GREEN}✓  Within target range${NC}"
    fi
    echo ""
fi

# --- Audit mode ---
if [ "$AUDIT" = true ]; then
    LAYOUT_FILE="poc-figma/src/utils/layout.ts"
    if [ -f "$LAYOUT_FILE" ]; then
        echo -e "${CYAN}▸ Audit: Current layout.ts vs Recommendations${NC}"
        echo ""

        extract_val() {
            grep "export const $1" "$LAYOUT_FILE" | grep -oE '[0-9]+' | head -1
        }

        audit_line() {
            local name="$1" current="$2" recommended="$3"
            if [ "$current" = "$recommended" ]; then
                echo -e "  ${GREEN}✓${NC} $name: ${current}  ${DIM}(matches)${NC}"
            else
                local diff=$((recommended - current))
                local direction="increase"
                [ "$diff" -lt 0 ] && direction="decrease" && diff=$((-diff))
                echo -e "  ${YELLOW}△${NC} $name: ${current} → ${GREEN}${recommended}${NC}  ${DIM}(${direction} by ${diff})${NC}"
            fi
        }

        audit_line "FONT_TITLE_HERO" "$(extract_val FONT_TITLE_HERO)" "$S1"
        audit_line "FONT_TITLE" "$(extract_val FONT_TITLE)" "$S2"
        audit_line "FONT_SUBTITLE" "$(extract_val FONT_SUBTITLE)" "$S3"
        audit_line "FONT_BULLET" "$(extract_val FONT_BULLET)" "$S4"
        audit_line "FONT_FOOTER" "$(extract_val FONT_FOOTER)" "$S5"
        audit_line "MARGIN_X" "$(extract_val MARGIN_X)" "$(echo "scale=0; $MARGIN_SIDE" | bc)"
        audit_line "MARGIN_Y" "$(extract_val MARGIN_Y)" "$(echo "scale=0; $MARGIN_TOP" | bc)"
        echo ""
    else
        echo -e "${YELLOW}layout.ts not found at ${LAYOUT_FILE}${NC}"
    fi
fi
