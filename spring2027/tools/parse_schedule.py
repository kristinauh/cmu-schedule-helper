#!/usr/bin/env python3
"""Parse CMU Full Schedule of Classes HTML into JSON."""

import json
import re
import sys
from html.parser import HTMLParser


class ScheduleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.semester = ""
        self.run_date = ""
        self.courses = []
        self.current_dept_name = ""
        self.current_course = None

        # Parse state
        self.in_td = False
        self.in_b = False
        self.td_index = 0
        self.row_cells = []
        self.cell_text = ""
        self.in_row = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self.in_row = True
            self.row_cells = []
            self.td_index = 0
        elif tag == "td":
            self.in_td = True
            self.cell_text = ""
        elif tag == "b":
            self.in_b = True
        elif tag == "br":
            pass

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "td":
            self.in_td = False
            self.row_cells.append(self.cell_text.strip())
            self.td_index += 1
        elif tag == "tr":
            self.in_row = False
            self.process_row(self.row_cells)
        elif tag == "b":
            self.in_b = False

    def handle_data(self, data):
        data_stripped = data.strip()
        if not data_stripped:
            return

        # Extract semester and run date from header
        if "Semester:" in data:
            self.semester = data.replace("Semester:", "").strip()
        if "Run Date:" in data:
            self.run_date = data.replace("Run Date:", "").strip()

        if self.in_td:
            self.cell_text += data

    def process_row(self, cells):
        if not cells:
            return

        # Filter out empty/nbsp cells
        clean = [c.replace("\xa0", "").strip() for c in cells]

        # Skip header row
        if clean and clean[0] == "Course":
            return
        # Skip empty spacer rows
        if all(c == "" for c in clean):
            return

        first = clean[0] if clean else ""

        # Department header: first cell has text, rest are empty, and it's bold
        # Department headers have a name in first cell and all other cells empty
        if first and not re.match(r"^\d{5}$", first):
            # Check if this looks like a department header (non-course-number text, other cells mostly empty)
            other_cells = clean[1:] if len(clean) > 1 else []
            if all(c == "" for c in other_cells) and not re.match(r"^\d", first):
                self.current_dept_name = first
                return

        # Course row: starts with 5-digit number
        if re.match(r"^\d{5}$", first):
            # Pad cells to expected length
            while len(clean) < 8:
                clean.append("")

            course_num = first
            title = clean[1]
            units = clean[2]
            sec_id = clean[3]
            days = clean[4]
            begin = clean[5]
            end = clean[6]
            loc = clean[7] if len(clean) > 7 else ""

            # Convert 5-digit to XX-XXX format
            dept = course_num[:2]
            num_formatted = f"{dept}-{course_num[2:]}"
            level = int(course_num[2]) * 100

            section = {}
            if sec_id:
                section["id"] = sec_id
            if days:
                section["days"] = days
            if begin:
                section["begin"] = begin
            if end:
                section["end"] = end
            if loc:
                section["loc"] = loc

            self.current_course = {
                "num": num_formatted,
                "dept": dept,
                "level": level,
                "title": title,
                "units": units,
                "deptName": self.current_dept_name,
                "sections": [section] if sec_id or days else [],
            }
            self.courses.append(self.current_course)

        # Continuation row: first cell is empty
        elif first == "" and self.current_course:
            while len(clean) < 8:
                clean.append("")

            title_cont = clean[1]
            sec_id = clean[3]
            days = clean[4]
            begin = clean[5]
            end = clean[6]
            loc = clean[7] if len(clean) > 7 else ""

            # Title continuation
            if title_cont and not sec_id and not days:
                self.current_course["title"] += " " + title_cont

            # Additional section
            if sec_id or days:
                # If there's also a title continuation on this row
                if title_cont:
                    self.current_course["title"] += " " + title_cont

                section = {}
                if sec_id:
                    section["id"] = sec_id
                if days:
                    section["days"] = days
                if begin:
                    section["begin"] = begin
                if end:
                    section["end"] = end
                if loc:
                    section["loc"] = loc
                self.current_course["sections"].append(section)


def parse_schedule(html_path, output_path=None):
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    # Fix malformed HTML: some rows missing <TR> tags
    html = re.sub(r"</TR>\s*<TD", "</TR>\n<TR><TD", html, flags=re.IGNORECASE)

    parser = ScheduleParser()
    parser.feed(html)

    result = {
        "semester": parser.semester,
        "updated": parser.run_date,
        "courses": parser.courses,
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(result, f, indent=None, separators=(",", ":"))
        print(f"Wrote {len(parser.courses)} courses to {output_path}")
        print(f"Semester: {parser.semester}")
        print(f"Run Date: {parser.run_date}")

        # Stats
        locs = set()
        for c in parser.courses:
            for s in c["sections"]:
                if s.get("loc"):
                    locs.add(s["loc"])
        print(f"Locations found: {sorted(locs)}")
    else:
        print(json.dumps(result, indent=2))

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 parse_schedule.py <input.html> [output.json]")
        sys.exit(1)
    html_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    parse_schedule(html_path, output_path)
