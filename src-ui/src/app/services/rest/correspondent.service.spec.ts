import { TestBed } from '@angular/core/testing';

import { CorrespondentService } from './correspondent.service';

describe('CorrespondentService', () => {
  let service: CorrespondentService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(CorrespondentService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
