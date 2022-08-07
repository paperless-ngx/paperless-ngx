import { TestBed } from '@angular/core/testing';

import { DocumentCommentService } from './document-comment.service';

describe('DocumentCommentService', () => {
  let service: DocumentCommentService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DocumentCommentService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});