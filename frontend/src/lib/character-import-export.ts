export interface CharacterImportData {
  name: string;
  description?: string;
  role?: string;
  age?: number;
  gender?: string;
  personality?: string;
  appearance?: string;
  voice?: string;
  background?: string;
  [key: string]: any;
}

export interface CharacterExportData extends CharacterImportData {
  id: string;
  novel_id: string;
  avatar?: string;
  created_at?: string;
  updated_at?: string;
}

export function parseCSV(csvText: string): CharacterImportData[] {
  const lines = csvText.trim().split("\n");
  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.trim().replace(/"/g, ""));
  const result: CharacterImportData[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length === 0) continue;

    const character: Record<string, any> = {};
    headers.forEach((header, index) => {
      const value = values[index] || "";
      if (header === "age") {
        character[header] = parseInt(value) || undefined;
      } else {
        character[header] = value;
      }
    });

    result.push(character as CharacterImportData);
  }

  return result;
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      result.push(current.trim().replace(/"/g, ""));
      current = "";
    } else {
      current += char;
    }
  }

  result.push(current.trim().replace(/"/g, ""));
  return result;
}

export function toCSV(characters: CharacterImportData[]): string {
  if (characters.length === 0) return "";

  const headers = Object.keys(characters[0]);
  const lines = [headers.join(",")];

  for (const char of characters) {
    const values = headers.map((h) => {
      const value = char[h];
      if (value === undefined || value === null) return "";
      const str = String(value);
      return str.includes(",") || str.includes('"') || str.includes("\n")
        ? `"${str.replace(/"/g, '""')}"`
        : str;
    });
    lines.push(values.join(","));
  }

  return lines.join("\n");
}

export function toJSON(
  characters: CharacterImportData[],
  pretty = true
): string {
  return JSON.stringify(characters, null, pretty ? 2 : 0);
}

export function fromJSON(jsonText: string): CharacterImportData[] {
  try {
    const data = JSON.parse(jsonText);
    if (Array.isArray(data)) {
      return data as CharacterImportData[];
    }
    if (data.characters && Array.isArray(data.characters)) {
      return data.characters as CharacterImportData[];
    }
    return [];
  } catch {
    throw new Error("Invalid JSON format");
  }
}

export async function importFromFile(
  file: File
): Promise<CharacterImportData[]> {
  const text = await file.text();
  const extension = file.name.split(".").pop()?.toLowerCase();

  switch (extension) {
    case "csv":
      return parseCSV(text);
    case "json":
      return fromJSON(text);
    default:
      throw new Error(`Unsupported file format: ${extension}`);
  }
}

export function exportToFile(
  characters: CharacterImportData[],
  format: "csv" | "json",
  filename = "characters"
): void {
  let content: string;
  let mimeType: string;
  let extension: string;

  switch (format) {
    case "csv":
      content = toCSV(characters);
      mimeType = "text/csv";
      extension = "csv";
      break;
    case "json":
      content = toJSON(characters);
      mimeType = "application/json";
      extension = "json";
      break;
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.${extension}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}