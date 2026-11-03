import { describe, expect, it } from 'vitest';
import { ACCEPTED_EXTENSIONS, fileExtensionLabel, hasAcceptedExtension } from '@/lib/constants';

describe('constants.ts', () => {
  describe('hasAcceptedExtension', () => {
    it.each(ACCEPTED_EXTENSIONS)('accepts %s', (ext) => {
      expect(hasAcceptedExtension(`contract${ext}`)).toBe(true);
    });

    it('is case-insensitive', () => {
      expect(hasAcceptedExtension('CONTRACT.PDF')).toBe(true);
      expect(hasAcceptedExtension('notes.TXT')).toBe(true);
    });

    it('rejects other extensions and extensionless names', () => {
      expect(hasAcceptedExtension('image.png')).toBe(false);
      expect(hasAcceptedExtension('archive.docx.bak')).toBe(false);
      expect(hasAcceptedExtension('noextension')).toBe(false);
      expect(hasAcceptedExtension('')).toBe(false);
    });
  });

  describe('fileExtensionLabel', () => {
    it('returns the lowercased extension with dot', () => {
      expect(fileExtensionLabel('Contract.PDF')).toBe('.pdf');
      expect(fileExtensionLabel('a/b/c.MD')).toBe('.md');
    });

    it('returns empty string when there is no extension', () => {
      expect(fileExtensionLabel('README')).toBe('');
      expect(fileExtensionLabel('')).toBe('');
    });
  });
});
