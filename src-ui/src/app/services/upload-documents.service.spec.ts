import { TestBed } from '@angular/core/testing';

import { UploadDocumentsService } from './upload-documents.service';

describe('UploadDocumentsService', () => {
  let service: UploadDocumentsService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(UploadDocumentsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
