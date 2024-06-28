import { TestBed } from '@angular/core/testing';

import { FoldersService } from './folders.service';

describe('FoldersService', () => {
  let service: FoldersService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(FoldersService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
