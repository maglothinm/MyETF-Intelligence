import React from 'react';

const Header = () => {
    return (
        <div className="header">
            <div className="header-left">
                <img
                    src={`${process.env.PUBLIC_URL}/polititrack-header-64.png`}
                    srcSet={`${process.env.PUBLIC_URL}/polititrack-header-128.png 2x`}
                    alt=""
                    width="50"
                    height="50"
                    className="logo"
                />
                <h1>PolitiTrack</h1>
            </div>
            <div className="header-right">
                {/* Search bar component */}
                <input type="text" placeholder="Search..." className="search-bar" />
            </div>
        </div>
    );
};

export default Header;
