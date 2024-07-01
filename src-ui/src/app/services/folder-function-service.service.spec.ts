import { TestBed } from '@angular/core/testing';

import { FolderFunctionServiceService } from './folder-function-service.service';

describe('FolderFunctionServiceService', () => {
  let service: FolderFunctionServiceService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(FolderFunctionServiceService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
