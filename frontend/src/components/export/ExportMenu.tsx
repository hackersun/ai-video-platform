'use client';

import { useState } from 'react';
import { FileDown, FileText, File, ChevronDown, Loader2 } from 'lucide-react';
import { jsPDF } from 'jspdf';
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx';
import { cn } from '@/lib/utils';

interface Chapter {
  id: string;
  title: string;
  content?: string;
  order: number;
}

interface ExportMenuProps {
  chapters: Chapter[];
  title?: string;
  className?: string;
}

type ExportFormat = 'pdf' | 'word' | 'txt';

interface ExportOption {
  format: ExportFormat;
  label: string;
  icon: React.ReactNode;
  description: string;
}

const exportOptions: ExportOption[] = [
  {
    format: 'pdf',
    label: 'PDF 文档',
    icon: <FileText className="w-4 h-4" />,
    description: '适合打印和分享',
  },
  {
    format: 'word',
    label: 'Word 文档',
    icon: <FileText className="w-4 h-4" />,
    description: '便于编辑和排版',
  },
  {
    format: 'txt',
    label: '纯文本',
    icon: <File className="w-4 h-4" />,
    description: '通用格式，轻量级',
  },
];

function stripHtml(html: string): string {
  const tmp = typeof document !== 'undefined' 
    ? document.createElement('div') 
    : null;
  if (tmp) {
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
  }
  return html.replace(/<[^>]*>/g, '');
}

function generatePdfContent(chapters: Chapter[], title: string): Blob {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  const contentWidth = pageWidth - margin * 2;
  let yPosition = 30;

  doc.setFontSize(20);
  doc.setFont('helvetica', 'bold');
  const titleWidth = doc.getTextWidth(title);
  doc.text(title, (pageWidth - titleWidth) / 2, yPosition);
  yPosition += 15;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(128, 128, 128);
  const date = new Date().toLocaleDateString('zh-CN');
  doc.text(`生成日期: ${date}`, margin, yPosition);
  yPosition += 15;
  doc.setTextColor(0, 0, 0);

  chapters.forEach((chapter, index) => {
    if (yPosition > 260) {
      doc.addPage();
      yPosition = 20;
    }

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text(`${index + 1}. ${chapter.title}`, margin, yPosition);
    yPosition += 10;

    doc.setFontSize(11);
    doc.setFont('helvetica', 'normal');
    const content = stripHtml(chapter.content || '');
    const lines = doc.splitTextToSize(content, contentWidth);
    
    lines.forEach((line: string) => {
      if (yPosition > 280) {
        doc.addPage();
        yPosition = 20;
      }
      doc.text(line, margin, yPosition);
      yPosition += 6;
    });

    yPosition += 10;
  });

  return doc.output('blob');
}

async function generateWordContent(chapters: Chapter[], title: string): Promise<Blob> {
  const children: Paragraph[] = [];

  children.push(
    new Paragraph({
      text: title,
      heading: HeadingLevel.TITLE,
      spacing: { after: 200 },
    })
  );

  children.push(
    new Paragraph({
      children: [
        new TextRun({
          text: `生成日期: ${new Date().toLocaleDateString('zh-CN')}`,
          italics: true,
          size: 20,
        }),
      ],
      spacing: { after: 400 },
    })
  );

  for (const chapter of chapters) {
    children.push(
      new Paragraph({
        text: chapter.title,
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 200, after: 100 },
      })
    );

    const content = stripHtml(chapter.content || '');
    children.push(
      new Paragraph({
        children: [
          new TextRun({
            text: content,
            size: 22,
          }),
        ],
        spacing: { after: 200 },
      })
    );
  }

  const doc = new Document({
    sections: [{
      properties: {},
      children,
    }],
  });

  return await Packer.toBlob(doc);
}

function generateTxtContent(chapters: Chapter[], title: string): string {
  const lines: string[] = [];
  
  lines.push(title);
  lines.push('='.repeat(title.length));
  lines.push(`生成日期: ${new Date().toLocaleDateString('zh-CN')}`);
  lines.push('');
  lines.push('');

  chapters.forEach((chapter, index) => {
    lines.push(`${index + 1}. ${chapter.title}`);
    lines.push('-'.repeat(20));
    const content = stripHtml(chapter.content || '');
    lines.push(content);
    lines.push('');
    lines.push('');
  });

  return lines.join('\n');
}

export function ExportMenu({ chapters, title = '文档导出', className }: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null);

  const handleExport = async (format: ExportFormat) => {
    setIsExporting(true);
    setExportingFormat(format);

    try {
      let blob: Blob;
      let filename: string;
      let mimeType: string;

      const safeTitle = title.replace(/[^a-zA-Z0-9\u4e00-\u9fa5]/g, '_');

      switch (format) {
        case 'pdf':
          blob = generatePdfContent(chapters, title);
          filename = `${safeTitle}.pdf`;
          mimeType = 'application/pdf';
          break;
        case 'word':
          blob = await generateWordContent(chapters, title);
          filename = `${safeTitle}.docx`;
          mimeType = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
          break;
        case 'txt':
          const txtContent = generateTxtContent(chapters, title);
          blob = new Blob([txtContent], { type: 'text/plain;charset=utf-8' });
          filename = `${safeTitle}.txt`;
          mimeType = 'text/plain';
          break;
        default:
          throw new Error('Unsupported format');
      }

      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setIsExporting(false);
      setExportingFormat(null);
      setIsOpen(false);
    }
  };

  return (
    <div className={cn('relative', className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isExporting || chapters.length === 0}
        className={cn(
          'inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all',
          'bg-gradient-to-r from-violet-600 to-purple-600 text-white',
          'hover:from-violet-500 hover:to-purple-500',
          'focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'shadow-lg shadow-violet-500/25'
        )}
      >
        {isExporting ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <FileDown className="w-4 h-4" />
        )}
        <span>导出</span>
        <ChevronDown className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-56 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-xl z-20 overflow-hidden">
            <div className="p-2">
              {exportOptions.map((option) => (
                <button
                  key={option.format}
                  onClick={() => handleExport(option.format)}
                  disabled={isExporting}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg',
                    'text-left transition-colors',
                    'hover:bg-gray-100 dark:hover:bg-gray-800',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  <span className="text-gray-500 dark:text-gray-400">
                    {isExporting && exportingFormat === option.format ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      option.icon
                    )}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-200">
                      {option.label}
                    </div>
                    <div className="text-xs text-gray-500">
                      {option.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
            {chapters.length === 0 && (
              <div className="px-3 py-2 text-xs text-gray-500 border-t border-gray-200 dark:border-gray-700">
                无内容可导出
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}