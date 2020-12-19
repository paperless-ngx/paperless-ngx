import { TestBed } from '@angular/core/testing';

import { OpenDocumentsService } from './open-documents.service';

describe('OpenDocumentsService', () => {
  let service: OpenDocumentsService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(OpenDocumentsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
