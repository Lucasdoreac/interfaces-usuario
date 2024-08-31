import React from 'react';
import './Home.scss';
import AvatarImage from '../../images/man.png';
import Button from '../../components/Button/Button';

const Home = () => {
  return (
    <div>
      <div className="card-header">
        <div className="row mb-4">
          <div className="col-md-3">

          </div>
        </div>
      </div>
      <div className="card-body">
        <div className="row">
          <div className="col-md-12 text-center">
            <img className="img-man" src={AvatarImage} style={{ width: '200px', }} alt="man avatar" />
            <div className="mt-4">
              <Button href="/organizador" className="btn" size="md" text="ORGANIZADOR" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;