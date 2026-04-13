#!/usr/bin/env bash
# Generate all brand × tool permutations with progress tracking.
#
# Runs tools in waves: pptx first (fast, parallel), then marp, then slidev.
# Within each wave, brands run in parallel up to MAX_PARALLEL.
#
# Usage: ./scripts/permutations.sh [CONTENT] [MAX_PARALLEL]

set -euo pipefail

CONTENT="${1:-investor-pitch.yaml}"
CONTENT_PREFIX="${CONTENT%.yaml}"
MAX_PARALLEL="${2:-4}"
BRANDS_DIR="brands"
DIST_DIR="dist/output"
ROOT_DIR="$(pwd)"

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
NC='\033[0m'

PROGRESS_FILE=$(mktemp)
: > "$PROGRESS_FILE"

brand_files=($(ls "$BRANDS_DIR"/*.yaml 2>/dev/null))
NUM_BRANDS=${#brand_files[@]}
TOTAL=$((NUM_BRANDS * 3))

echo -e "${CYAN}━━━ Permutation Generator ━━━${NC}"
echo "Brands:   ${NUM_BRANDS}"
echo "Tools:    3 (pptx → marp → slidev)"
echo "Total:    ${TOTAL} decks"
echo "Parallel: ${MAX_PARALLEL} per wave"
echo ""

echo "Building images..."
docker compose build marp-pptx slidev-pptx pptx > /dev/null 2>&1
echo "Images ready."
echo ""

generate_pptx() {
    local brand_file="$1"
    local brand_name
    brand_name=$(basename "$brand_file" .yaml)
    local out_dir="${DIST_DIR}/${brand_name}/pptx"
    mkdir -p "${ROOT_DIR}/${out_dir}"

    if docker compose run --rm -T \
        -v "${ROOT_DIR}/${brand_file}:/data/brand.yaml:ro" \
        -v "${ROOT_DIR}/${out_dir}:/app/output" \
        pptx /data/content/"${CONTENT}" /data/brand.yaml \
        > /dev/null 2>&1; then
        mv "${out_dir}/deck.pptx" "${out_dir}/${CONTENT_PREFIX}-pptx.pptx" 2>/dev/null || true
        echo "done ${brand_name} pptx" >> "$PROGRESS_FILE"
    else
        echo "fail ${brand_name} pptx" >> "$PROGRESS_FILE"
    fi
    local c; c=$(wc -l < "$PROGRESS_FILE" | tr -d ' ')
    echo -ne "\r  [${c}/${TOTAL}] ${brand_name}/pptx            "
}

generate_marp() {
    local brand_file="$1"
    local brand_name
    brand_name=$(basename "$brand_file" .yaml)
    local out_dir="${DIST_DIR}/${brand_name}/marp"
    mkdir -p "${ROOT_DIR}/${out_dir}"

    if docker compose run --rm -T \
        -v "${ROOT_DIR}/${brand_file}:/data/brand.yaml:ro" \
        -v "${ROOT_DIR}/${out_dir}:/app/output" \
        --entrypoint sh marp-pptx -c \
        "node generate.js /data/content/${CONTENT} /data/brand.yaml && npx @marp-team/marp-cli --allow-local-files output/deck.md --pptx -o output/${CONTENT_PREFIX}-marp.pptx" \
        > /dev/null 2>&1; then
        echo "done ${brand_name} marp" >> "$PROGRESS_FILE"
    else
        echo "fail ${brand_name} marp" >> "$PROGRESS_FILE"
    fi
    local c; c=$(wc -l < "$PROGRESS_FILE" | tr -d ' ')
    echo -ne "\r  [${c}/${TOTAL}] ${brand_name}/marp            "
}

generate_slidev() {
    local brand_file="$1"
    local brand_name
    brand_name=$(basename "$brand_file" .yaml)
    local out_dir="${DIST_DIR}/${brand_name}/slidev"
    mkdir -p "${ROOT_DIR}/${out_dir}"

    if docker compose run --rm -T \
        -v "${ROOT_DIR}/${brand_file}:/data/brand.yaml:ro" \
        -v "${ROOT_DIR}/${out_dir}:/app/output" \
        --entrypoint sh slidev-pptx -c \
        "node generate.js /data/content/${CONTENT} /data/brand.yaml && slidev export output/slides.md --output output/${CONTENT_PREFIX}-slidev.pptx --format pptx --timeout 60000" \
        > /dev/null 2>&1; then
        echo "done ${brand_name} slidev" >> "$PROGRESS_FILE"
    else
        echo "fail ${brand_name} slidev" >> "$PROGRESS_FILE"
    fi
    local c; c=$(wc -l < "$PROGRESS_FILE" | tr -d ' ')
    echo -ne "\r  [${c}/${TOTAL}] ${brand_name}/slidev          "
}

START=$(date +%s)

# Copy source content to each brand dir
for brand_file in "${brand_files[@]}"; do
    brand_name=$(basename "$brand_file" .yaml)
    mkdir -p "${DIST_DIR}/${brand_name}"
    cp -f "content/${CONTENT}" "${DIST_DIR}/${brand_name}/${CONTENT}" 2>/dev/null || true
done

# Wave 1: python-pptx (fastest, ~1s each)
echo -e "${YELLOW}Wave 1: python-pptx (${NUM_BRANDS} brands)${NC}"
job_count=0
for brand_file in "${brand_files[@]}"; do
    generate_pptx "$brand_file" &
    job_count=$((job_count + 1))
    while [ "$job_count" -ge "$MAX_PARALLEL" ]; do
        wait -n 2>/dev/null || true; job_count=$((job_count - 1))
    done
done
wait
echo ""

# Wave 2: Marp (~5s each) — sequential, Chromium hangs under parallel load
echo -e "${YELLOW}Wave 2: Marp (${NUM_BRANDS} brands, sequential — Chromium)${NC}"
for brand_file in "${brand_files[@]}"; do
    generate_marp "$brand_file"
done
echo ""

# Wave 3: Slidev (~12s each) — sequential, also Chromium-based
echo -e "${YELLOW}Wave 3: Slidev (${NUM_BRANDS} brands, sequential — Chromium)${NC}"
for brand_file in "${brand_files[@]}"; do
    generate_slidev "$brand_file"
done
echo ""

ELAPSED=$(( $(date +%s) - START ))

echo ""
DONE_COUNT=$(grep -c "^done" "$PROGRESS_FILE" 2>/dev/null || echo 0)
FAIL_COUNT=$(grep -c "^fail" "$PROGRESS_FILE" 2>/dev/null || echo 0)

echo -e "${CYAN}━━━ Results ━━━${NC}"
echo -e "${GREEN}  ✓ Success: ${DONE_COUNT}/${TOTAL}${NC}"
if [ "$FAIL_COUNT" -gt 0 ]; then
    echo -e "${RED}  ✗ Failed:  ${FAIL_COUNT}${NC}"
    grep "^fail" "$PROGRESS_FILE" | while read _ brand tool; do
        echo -e "    ${RED}✗ ${brand} / ${tool}${NC}"
    done
fi
echo "  ⏱  Total: ${ELAPSED}s"
echo ""

TOTAL_FILES=$(find "$DIST_DIR" -name "*.pptx" 2>/dev/null | wc -l | tr -d ' ')
echo "  📁 ${TOTAL_FILES} decks in ${DIST_DIR}/"

rm -f "$PROGRESS_FILE"
